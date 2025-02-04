import requests
import json
import os
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Ganti dengan token bot Anda
TOKEN = os.environ.get('YOUR_TELEGRAM_BOT_TOKEN')

# File untuk menyimpan token favorit
FAVORITES_FILE = 'favorites.json'

# File untuk menyimpan pair yang sudah dideteksi
DETECTED_PAIRS_FILE = 'detected_pairs.json'

# Jaringan yang dipantau
NETWORKS = ['ethereum', 'bsc', 'polygon']

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# Fungsi untuk memuat pair yang sudah dideteksi
def load_detected_pairs():
    if os.path.exists(DETECTED_PAIRS_FILE):
        with open(DETECTED_PAIRS_FILE, 'r') as file:
            return json.load(file)
    return []

# Fungsi untuk menyimpan pair yang sudah dideteksi
def save_detected_pairs(detected_pairs):
    with open(DETECTED_PAIRS_FILE, 'w') as file:
        json.dump(detected_pairs, file)

# Fungsi untuk mendapatkan data pair dari DexScreener
async def get_pair_data(pair_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/{pair_address}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('pair', {})
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching pair data: {e}")
        return {}

# Fungsi untuk mencari pair dari DexScreener
async def search_pair(query):
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('pairs', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching pair: {e}")
        return []

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
    pairs = await search_pair(user_input)

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

# Fungsi untuk memeriksa new pair dan mengirim notifikasi
async def check_new_pairs(context: CallbackContext):
    detected_pairs = load_detected_pairs()

    for network in NETWORKS:
        new_pairs = await search_pair(network)
        time.sleep(1)  # Jeda 1 detik antara setiap permintaan

        for pair in new_pairs:
            pair_address = pair['pairAddress']
            if pair_address not in detected_pairs:
                # Kirim notifikasi ke chat atau grup
                base_token = pair['baseToken']['name']
                quote_token = pair['quoteToken']['symbol']
                price_usd = pair['priceUsd']
                liquidity = pair['liquidity']['usd']
                fdv = pair['fdv']
                price_change = pair['priceChange']['h24']

                # Buat tombol Buy
                keyboard = [
                    [InlineKeyboardButton("Buy", url=f"https://dexscreener.com/{network}/{pair_address}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Kirim pesan dengan tombol
                message = (
                    f"🚀 New Pair Detected!\n"
                    f"🔹 Network: {network}\n"
                    f"🔹 Pair: {base_token}/{quote_token}\n"
                    f"🔹 Harga: ${price_usd}\n"
                    f"🔹 Liquidity: ${liquidity:,.2f}\n"
                    f"🔹 FDV: ${fdv:,.2f}\n"
                    f"🔹 24h Change: {price_change:.2f}%"
                )
                await context.bot.send_message(chat_id=CHAT_ID, text=message, reply_markup=reply_markup)

                # Simpan pair yang sudah dideteksi
                detected_pairs.append(pair_address)
                save_detected_pairs(detected_pairs)

# Main function
def main():
    # Inisialisasi Application
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addfavorite", add_favorite))
    application.add_handler(CommandHandler("listfavorites", list_favorites))
    application.add_handler(CommandHandler("removefavorite", remove_favorite))

    # Message handler untuk pesan teks biasa
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Jadwalkan pengecekan new pair setiap 5 menit
    application.job_queue.run_repeating(check_new_pairs, interval=300, first=0)  # 300 detik = 5 menit

    # Mulai bot
    application.run_polling()

if __name__ == '__main__':
    # Ganti dengan chat ID tujuan (bisa chat pribadi atau grup)
    CHAT_ID = 'YOUR_CHAT_ID'  # Contoh: 123456789 (chat pribadi) atau -1001234567890 (grup)
    main()
