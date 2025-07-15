import logging
import random
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = "7584730200:AAHuPCy609l914vPKhNlohEzWYOuLzfkffg"
MAX_ATTEMPTS = 3
CAPTCHA_TIMEOUT = 60

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

captcha_data = {}

GROUP_IDS = {
    "genshin_imapct": -1002840180262,
    "wuthering_waves": -1002443942396,
    "honkai": -1002437082497
}

def generate_captcha():
    x = random.randint(1, 9)
    y = random.randint(1, 9)
    result = x + y
    question = f"{x} + {y} = ?"

    img = Image.new("RGB", (200, 80), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        font = ImageFont.load_default()

    for _ in range(50):
        x_p = random.randint(0, 200)
        y_p = random.randint(0, 80)
        draw.point((x_p, y_p), fill=(
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        ))

    draw.text((40, 20), question, fill=(0, 0, 0), font=font)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return result, buffer, question

async def cleanup_captchas(context: ContextTypes.DEFAULT_TYPE):
    current_time = time.time()
    expired = [user_id for user_id, data in captcha_data.items() 
                if current_time - data['timestamp'] > CAPTCHA_TIMEOUT]
    
    for user_id in expired:
        del captcha_data[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    args = context.args
    group_code = None
    if args:
        code = args[0]
        if code in GROUP_IDS:
            group_code = code
        else:
            await update.message.reply_text("لا يمكن استخدام البوت يرجى استخدام رابط المجموعة الصحيح.")
            return
    else:
        await update.message.reply_text("لا يمكن استخدام البوت بدون كود المجموعة. يرجى استخدام رابط المجموعة الصحيح.")
        return

    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    answer, image, question = generate_captcha()
    captcha_data[user_id] = {
        "answer": answer,
        "attempts": 0,
        "timestamp": time.time(),
        "group_code": group_code
    }
    await update.message.reply_photo(
        photo=image,
        caption=f"مرحباً {first_name}!\nحل المسألة الرياضية:\n\nلديك {MAX_ATTEMPTS} محاولات."
    )

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    if user_id not in captcha_data:
        await update.message.reply_text("⚠️ الرجاء إرسال /start أولاً")
        return

    data = captcha_data[user_id]

    if time.time() - data['timestamp'] > CAPTCHA_TIMEOUT:
        del captcha_data[user_id]
        await update.message.reply_text("⏰ انتهت صلاحية الكابتشا، أرسل /start لبدء جديدة")
        return

    try:
        answer = int(user_input)
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح")
        return

    if answer == data['answer']:
        try:
            group_code = data.get("group_code")
            if not group_code or group_code not in GROUP_IDS:
                await update.message.reply_text("❌ لا يوجد مجموعة مرتبطة بهذا الرابط.")
                del captcha_data[user_id]
                return

            group_id = GROUP_IDS[group_code]
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=group_id,
                member_limit=1,
                name=f"invite_{user_id}",
                creates_join_request=False
            )

            await update.message.reply_text(
                f"✅ تم التحقق بنجاح!\n\nرابط الدخول:\n{invite_link.invite_link}"
            )
            del captcha_data[user_id]
        except Exception as e:
            logger.error(f"خطأ في إنشاء الرابط: {str(e)}")
            error_msg = "⚠️ حدث خطأ في إنشاء الرابط. تأكد من:\n"
            error_msg += "1. أن البوت مشرف في المجموعة\n"
            error_msg += "2. أن ID المجموعة صحيح\n"
            error_msg += "3. أن البوت لديه صلاحية إنشاء روابط دعوة"
            await update.message.reply_text(error_msg)
    else:
        await update.message.reply_text("❌ الكود الذي أدخلته غير صحيح، حاول مرة أخرى.")


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response))
    
    job_queue = application.job_queue
    job_queue.run_repeating(cleanup_captchas, interval=300, first=10)

    logger.info("🤖 البوت يعمل...")
    application.run_polling()

if __name__ == "__main__":
    main()
