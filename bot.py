import requests
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application,JobQueue, CommandHandler, MessageHandler, filters, CallbackContext

# Ganti dengan token bot Anda
TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'

# File untuk menyimpan token favorit
FAVORITES_FILE = 'favorites.json'

# Fungsi untuk memuat token favorit dari file
def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, 'r') as file:
            return json.load(file)
    return {}

# Fungsi untuk menyimpan token favorit ke file
def save_favorites(favorites):
    with open(FAVORITES_FILE, 'w') as file:
        json.dump(favorites, file)

# Fungsi untuk mendapatkan data pair dari DexScreener
def get_pair_data(pair_address):
    url = f"https://api.dexscreener.com/latest/dex/pairs/{pair_address}"
    response = requests.get(url)
    data = response.json()
    return data.get('pair', {})

# Fungsi untuk mencari pair dari DexScreener
def search_pair(query):
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    response = requests.get(url)
    data = response.json()
    return data.get('pairs', [])

# Command /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        'Selamat datang! Gunakan perintah berikut:\n'
        '/addfavorite <pair_address> - Tambahkan pair favorit\n'
        '/listfavorites - Lihat daftar pair favorit\n'
        '/removefavorite <pair_address> - Hapus pair favorit\n'
        'Anda juga bisa mengirim ticker atau nama token untuk melihat harganya.'
    )

# Command /addfavorite
async def add_favorite(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    pair_address = ' '.join(context.args).strip()

    if not pair_address:
        await update.message.reply_text('Masukkan alamat pair. Contoh: /addfavorite 0x123...')
        return

    favorites = load_favorites()
    if str(user_id) not in favorites:
        favorites[str(user_id)] = []

    if pair_address in favorites[str(user_id)]:
        await update.message.reply_text('Pair sudah ada di daftar favorit.')
    else:
        favorites[str(user_id)].append(pair_address)
        save_favorites(favorites)
        await update.message.reply_text(f'Pair {pair_address} berhasil ditambahkan ke favorit.')

# Command /listfavorites
async def list_favorites(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    favorites = load_favorites()

    if str(user_id) not in favorites or not favorites[str(user_id)]:
        await update.message.reply_text('Anda belum menambahkan pair favorit.')
    else:
        message = "Daftar Pair Favorit Anda:\n"
        for pair in favorites[str(user_id)]:
            message += f"- {pair}\n"
        await update.message.reply_text(message)

# Command /removefavorite
async def remove_favorite(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    pair_address = ' '.join(context.args).strip()

    if not pair_address:
        await update.message.reply_text('Masukkan alamat pair. Contoh: /removefavorite 0x123...')
        return

    favorites = load_favorites()
    if str(user_id) not in favorites or pair_address not in favorites[str(user_id)]:
        await update.message.reply_text('Pair tidak ditemukan di daftar favorit.')
    else:
        favorites[str(user_id)].remove(pair_address)
        save_favorites(favorites)
        await update.message.reply_text(f'Pair {pair_address} berhasil dihapus dari favorit.')

# Handler untuk pesan teks biasa (cari pair berdasarkan ticker atau nama)
async def handle_message(update: Update, context: CallbackContext):
    user_input = update.message.text.strip().lower()
    pairs = search_pair(user_input)

    if not pairs:
        await update.message.reply_text('Pair tidak ditemukan. Coba lagi dengan ticker atau nama yang valid.')
        return

    pair = pairs[0]
    pair_address = pair['pairAddress']
    base_token = pair['baseToken']['name']
    quote_token = pair['quoteToken']['symbol']
    price_usd = pair['priceUsd']
    liquidity = pair['liquidity']['usd']
    fdv = pair['fdv']
    price_change = pair['priceChange']['h24']

    # Buat tombol Buy
    keyboard = [
        [InlineKeyboardButton("Buy", url=f"https://dexscreener.com/{pair['chainId']}/{pair_address}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Kirim pesan dengan tombol
    message = (
        f"🔍 Pair Ditemukan!\n"
        f"🔹 Pair: {base_token}/{quote_token}\n"
        f"🔹 Harga: ${price_usd}\n"
        f"🔹 Liquidity: ${liquidity:,.2f}\n"
        f"🔹 FDV: ${fdv:,.2f}\n"
        f"🔹 24h Change: {price_change:.2f}%"
    )
    await update.message.reply_text(message, reply_markup=reply_markup)

# Fungsi untuk memeriksa harga pair favorit
async def check_favorite_prices(context: CallbackContext):
    favorites = load_favorites()
    for user_id, pairs in favorites.items():
        for pair_address in pairs:
            pair_data = get_pair_data(pair_address)
            if pair_data:
                base_token = pair_data['baseToken']['name']
                quote_token = pair_data['quoteToken']['symbol']
                price_usd = pair_data['priceUsd']
                price_change = pair_data['priceChange']['h24']
                message = (
                    f"💰 Harga Pair Favorit\n"
                    f"🔹 Pair: {base_token}/{quote_token}\n"
                    f"🔹 Harga: ${price_usd}\n"
                    f"🔹 24h Change: {price_change:.2f}%"
                )
                await context.bot.send_message(chat_id=user_id, text=message)

# Main function
def main():
    # Inisialisasi Application
    application = Application.builder().token(TOKEN).build()

    # Pastikan job_queue aktif
    job_queue = application.job_queue
    if job_queue is None:
        raise ValueError("JobQueue tidak tersedia! Pastikan PTB diinstal dengan job-queue.")

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addfavorite", add_favorite))
    application.add_handler(CommandHandler("listfavorites", list_favorites))
    application.add_handler(CommandHandler("removefavorite", remove_favorite))

    # Message handler untuk pesan teks biasa
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Jadwalkan pengecekan harga pair favorit setiap 1 jam
    application.job_queue.run_repeating(check_favorite_prices, interval=3600, first=0)  # 3600 detik = 1 jam

    # Mulai bot
    application.run_polling()

if __name__ == '__main__':
    main()
