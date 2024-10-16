from flask import Flask, render_template, request, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext
import threading
import asyncio
import nest_asyncio
import requests

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'  # Necessário para usar sessões
nest_asyncio.apply()

# Variáveis globais
telegram_token = ""
messages = {
    "welcome": ["Olá! Eu sou seu bot. Como posso ajudar?"],
    "call_to_action": ["Clique no botão abaixo para ver nossos produtos!"],
    "products": [
        {"title": "Básico", "price": 9.99},
        {"title": "Médio", "price": 14.00},
        {"title": "Grande", "price": 19.00},
        {"title": "Completo", "price": 25.00}
    ]
}

# Função para o comando /start
async def start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("Ver Produtos", callback_data='show_products')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = messages["welcome"][0]
    call_to_action_message = messages["call_to_action"][0]
    
    await update.message.reply_text(f"{welcome_message}\n\n{call_to_action_message}", reply_markup=reply_markup)

# Função para mostrar produtos
async def show_products(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton(product['title'], callback_data=product['title'])] for product in messages["products"]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text="Aqui estão os nossos produtos:", reply_markup=reply_markup)

# Função para lidar com seleções de produtos
async def handle_product_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    selected_product = query.data

    await query.edit_message_text(text=f"Você selecionou: {selected_product}\n\nClique para finalizar a compra.")

# Função para mensagens não reconhecidas
async def handle_message(update: Update, context: CallbackContext):
    await update.message.reply_text("Desculpe, não entendi. Use /start para iniciar.")

# Função para executar o bot
async def run_bot(token):
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_products, pattern='show_products'))
    application.add_handler(CallbackQueryHandler(handle_product_selection))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Iniciando o bot...")
    await application.run_polling()

# Função para iniciar o bot em um thread
def start_bot(token):
    asyncio.run(run_bot(token))

# Rota principal
@app.route('/')
def index():
    return render_template('index.html')

# Rota para configurar o bot
@app.route('/configurar_bot', methods=['GET', 'POST'])
def configurar_bot_view():
    global telegram_token
    if request.method == 'POST':
        telegram_token = request.form['telegram_token']
        threading.Thread(target=start_bot, args=(telegram_token,), daemon=True).start()
        return redirect('/configurar_bot')
    
    return render_template('configurar_bot.html', token=telegram_token)

# Rota para configuração de mensagens
@app.route('/configuracao_mensagens', methods=['GET', 'POST'])
def configuracao_mensagens_view():
    global messages
    if request.method == 'POST':
        messages["welcome"] = [request.form['welcome_message']]
        messages["call_to_action"] = [request.form['call_to_action_message']]
        return redirect('/configuracao_mensagens')

    return render_template('configuracao_mensagens.html', 
                           welcome_message=messages["welcome"][0],
                           call_to_action_message=messages["call_to_action"][0])

# Rota para gerenciar mensagens de produtos
@app.route('/mensagens', methods=['GET', 'POST'])
def mensagens_view():
    global messages
    if request.method == 'POST':
        messages["welcome"] = [request.form['welcome_message']]
        messages["call_to_action"] = [request.form['call_to_action_message']]
        return {"success": True, "messages": messages}

    return render_template('mensagens.html', messages=messages)

# Rota para gerenciar produtos
@app.route('/produtos')
def produtos_view():
    return render_template('produtos.html', products=messages["products"])

# Rota para integrações
@app.route('/integracoes')
def integracoes_view():
    return render_template('integracoes.html')

# Rota para integrar conta com Mercado Pago
@app.route('/integrar_mercadolivre')
def integrar_mercadolivre():
    client_id = '5197116344501139'  # Coloque seu Client ID aqui
    redirect_uri = 'http://127.0.0.1:5000/callback'  # A URL de callback que você irá definir
    auth_url = f"https://auth.mercadopago.com.br/authorization?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}"
    return redirect(auth_url)

# Rota de callback para receber o token de acesso
@app.route('/callback')
def callback():
    code = request.args.get('code')  # O código de autorização
    if not code:
        return "Código de autorização não recebido", 400

    client_id = '5197116344501139'  # Coloque seu Client ID aqui
    client_secret = 'jFRXoPYZ3q6L5tz1M6e6TNJzYSF8UoM2'  # Coloque seu Client Secret aqui
    redirect_uri = 'http://127.0.0.1:5000/callback'
    
    # Troque o código de autorização por um token de acesso
    token_url = 'https://api.mercadopago.com/oauth/token'
    response = requests.post(token_url, data={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    })
    
    if response.status_code == 200:
        access_token = response.json().get('access_token')
        session['access_token'] = access_token  # Armazena o access_token na sessão
        return redirect('/?message=Conta integrada com sucesso!')
    else:
        return f"Falha na integração: {response.text}", response.status_code

# Rota para fazer uma venda
@app.route('/fazer_venda', methods=['POST'])
def fazer_venda():
    access_token = session.get('access_token')
    if not access_token:
        return "Usuário não autenticado", 401
    
    selected_product = request.form.get('product')
    
    product = next((p for p in messages["products"] if p["title"] == selected_product), None)
    if not product:
        return "Produto não encontrado", 404

    # Criando a preferência de pagamento
    preference_data = {
        "items": [
            {
                "title": product["title"],
                "quantity": 1,
                "unit_price": product["price"]
            }
        ],
        "back_urls": {
            "success": "http://127.0.0.1:5000/sucesso",
            "failure": "http://127.0.0.1:5000/falha",
            "pending": "http://127.0.0.1:5000/pendente"
        },
        "auto_return": "approved"
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post('https://api.mercadopago.com/v1/payments', headers=headers, json=preference_data)

    if response.status_code == 200:
        payment_url = response.json().get('init_point')  # URL para o pagamento
        return redirect(payment_url)  # Redireciona o usuário para a página de pagamento
    else:
        return f"Erro ao criar a venda: {response.text}", response.status_code

# Rotas para resultados de pagamento
@app.route('/sucesso')
def sucesso():
    return "Pagamento realizado com sucesso!"

@app.route('/falha')
def falha():
    return "Pagamento falhou."

@app.route('/pendente')
def pendente():
    return "Pagamento pendente."

# Executa o aplicativo Flask
if __name__ == '__main__':
    app.run(debug=True, port=5000)