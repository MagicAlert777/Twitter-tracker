import json
import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types

class TwitterTelegramBot:
    def __init__(self, telegram_token, chat_id, discord_webhook_url=None):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.discord_webhook_url = discord_webhook_url
        self.bot = Bot(token=telegram_token)
        self.dp = Dispatcher(self.bot)
    
    def clean_text(self, text):
        """Remove t.co links from text"""
        if not text:
            return ""
        words = text.split()
        cleaned_words = [word for word in words if not word.startswith('https://t.co/')]
        return ' '.join(cleaned_words)
    
    def format_username(self, username, for_discord=False):
        """Format username with Twitter profile link"""
        if for_discord:
            return f'[{username}](https://x.com/{username})'
        else:
            return f'<a href="https://x.com/{username}">{username}</a>'
    
    async def send_message_async(self, message, media_url=None, message_thread_id=None):
        """Send message to Telegram with optional media (photo or video)"""
        try:
            if media_url:
                print(f"[DEBUG] Отправляем сообщение с медиа: {media_url}")
                
                # Определяем тип медиа по расширению или содержимому URL
                media_type = "unknown"
                if any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    media_type = "photo"
                elif '.mp4' in media_url.lower() or 'video' in media_url.lower():
                    media_type = "video"
                
                print(f"[DEBUG] Определен тип медиа: {media_type}")
                
                try:
                    if media_type == "photo":
                        # Отправляем фото по ссылке с текстом в подписи
                        print(f"[DEBUG] Отправляем фото по URL: {media_url}")
                        await self.bot.send_photo(
                            chat_id=self.chat_id,
                            photo=media_url,
                            caption=message,
                            parse_mode=types.ParseMode.HTML,
                            message_thread_id=1601
                        )
                        print(f"[DEBUG] Сообщение с фото успешно отправлено")
                        return True
                    elif media_type == "video":
                        # Отправляем видео по ссылке с текстом в подписи
                        print(f"[DEBUG] Отправляем видео по URL: {media_url}")
                        await self.bot.send_video(
                            chat_id=self.chat_id,
                            video=media_url,
                            caption=message,
                            parse_mode=types.ParseMode.HTML,
                            message_thread_id=1601
                        )
                        print(f"[DEBUG] Сообщение с видео успешно отправлено")
                        return True
                except Exception as e:
                    print(f"[ERROR] Ошибка при отправке медиа по URL: {e}")
                    print(f"[DEBUG] Отправляем только текст (без медиа)")
            
            # Отправляем только текст если нет медиа или если не удалось отправить медиа
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=types.ParseMode.HTML,
                disable_web_page_preview=False,  # Отключаем предпросмотр ссылок
                message_thread_id=1601
            )
            print(f"[DEBUG] Текстовое сообщение успешно отправлено")
            return True
            
        except Exception as e:
            print(f"[ERROR] Ошибка отправки сообщения в Telegram: {e}")
            import traceback
            print(traceback.format_exc())
            return False
    
    def send_message(self, message, media_url=None):
        """Wrapper for async message sending to Telegram"""
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # Передаем сообщение без message_thread_id
        telegram_result = loop.run_until_complete(self.send_message_async(message, media_url))
        
        # Также отправляем в Discord, если настроен вебхук
        if self.discord_webhook_url:
            discord_result = self.send_to_discord(message, media_url)
            return telegram_result and discord_result
        
        return telegram_result
    
    def send_to_discord(self, message, media_url=None):
        """Send message to Discord via webhook"""
        if not self.discord_webhook_url:
            return False
        
        try:
            # Конвертируем HTML-форматирование в Markdown для Discord
            discord_message = message.replace('<b>', '**').replace('</b>', '**')
            discord_message = discord_message.replace('<i>', '*').replace('</i>', '*')
            discord_message = discord_message.replace('<u>', '__').replace('</u>', '__')
            discord_message = discord_message.replace('<s>', '~~').replace('</s>', '~~')
            
            # Заменяем HTML-ссылки на Markdown-ссылки
            import re
            html_links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', discord_message)
            for url, text in html_links:
                discord_message = discord_message.replace(f'<a href="{url}">{text}</a>', f'[{text}]({url})')
            
            # Создаем основной контент сообщения
            payload = {
                "content": discord_message
            }
            
            # Если есть медиа, добавляем его как дополнительное поле
            if media_url:
                media_type = "image" if any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) else "video"
                
                if media_type == "image":
                    # Для изображений создаем эмбед
                    payload["embeds"] = [
                        {
                            "image": {
                                "url": media_url
                            }
                        }
                    ]
                else:
                    # Для видео просто добавляем ссылку в конец сообщения
                    payload["content"] += f"\n\n[Видео]({media_url})"
            
            # Отправляем запрос к вебхуку Discord
            response = requests.post(
                self.discord_webhook_url,
                json=payload
            )
            
            if response.status_code == 204:
                print(f"[DEBUG] Сообщение успешно отправлено в Discord")
                return True
            else:
                print(f"[ERROR] Ошибка отправки в Discord: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Ошибка отправки сообщения в Discord: {e}")
            import traceback
            print(traceback.format_exc())
            return False
    
    def send_additional_photo_to_discord(self, caption, photo_url):
        """Send additional photo to Discord"""
        if not self.discord_webhook_url:
            return False
        
        try:
            payload = {
                "content": caption,
                "embeds": [
                    {
                        "image": {
                            "url": photo_url
                        }
                    }
                ]
            }
            
            response = requests.post(
                self.discord_webhook_url,
                json=payload
            )
            
            if response.status_code == 204:
                print(f"[DEBUG] Дополнительное фото успешно отправлено в Discord")
                return True
            else:
                print(f"[ERROR] Ошибка отправки фото в Discord: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Ошибка отправки фото в Discord: {e}")
            return False

    def process_tweet(self, tweet_data):
        """Process tweet data and send to Telegram and Discord"""
        try:
            print("[DEBUG] Проверяем наличие твитов в данных")
            tweets = tweet_data.get('tweets', [])
            if not tweets:
                print("[DEBUG] Список твитов пуст")
                return False
            
            tweet = tweets[0]
            if not tweet:
                print("[DEBUG] Первый твит в списке пуст")
                return False
            
            # Базовая информация о твите
            tweet_id = tweet.get('id', 'нет ID')
            author = tweet.get('author', {})
            username = author.get('userName', '')
            text = self.clean_text(tweet.get('text', ''))
            
            print(f"[DEBUG] Обрабатываем твит ID:{tweet_id} от {username}")
            print(f"[DEBUG] Текст твита: {text[:100]}...")
            
            # Поиск медиа (видео или фото) в оригинальном твите
            video_url = None
            photo_urls = []
            
            # Проверяем различные поля, где может быть медиа
            print("[DEBUG] Ищем медиа в твите...")
            
            # 1. Проверяем поле extendedEntities
            extended_entities = tweet.get('extendedEntities', {})
            if extended_entities:
                print("[DEBUG] Найдено поле extendedEntities")
                media = extended_entities.get('media', [])
                for item in media:
                    media_type = item.get('type', '')
                    print(f"[DEBUG] Тип медиа: {media_type}")
                    
                    # Проверяем на фото
                    if media_type == 'photo':
                        photo_url = item.get('media_url_https')
                        if photo_url:
                            photo_urls.append(photo_url)
                            print(f"[DEBUG] Найдено фото: {photo_url}")
                    
                    # Проверяем на видео
                    elif media_type == 'video' or media_type == 'animated_gif':
                        print("[DEBUG] Найдено видео в extendedEntities")
                        variants = item.get('video_info', {}).get('variants', [])
                        # Сортируем варианты по битрейту (качеству) в убывающем порядке
                        sorted_variants = sorted(variants, key=lambda x: x.get('bitrate', 0), reverse=True)
                        for variant in sorted_variants:
                            content_type = variant.get('content_type', '')
                            print(f"[DEBUG] Вариант видео: {content_type}, URL: {variant.get('url')}")
                            if content_type == 'video/mp4':
                                video_url = variant.get('url')
                                print(f"[DEBUG] Выбран вариант видео MP4: {video_url}")
                                break
                        if video_url:
                            break
            
            # 2. Проверяем поле entities
            if not video_url and not photo_urls:
                entities = tweet.get('entities', {})
                if entities:
                    print("[DEBUG] Проверяем поле entities")
                    media = entities.get('media', [])
                    for item in media:
                        media_type = item.get('type', '')
                        
                        # Проверяем на фото
                        if media_type == 'photo':
                            photo_url = item.get('media_url_https')
                            if photo_url:
                                photo_urls.append(photo_url)
                                print(f"[DEBUG] Найдено фото в entities: {photo_url}")
                        
                        # Проверяем на видео
                        elif media_type == 'video' or media_type == 'animated_gif':
                            print("[DEBUG] Найдено видео в entities")
                            variants = item.get('video_info', {}).get('variants', [])
                            for variant in variants:
                                if variant.get('content_type') == 'video/mp4':
                                    video_url = variant.get('url')
                                    print(f"[DEBUG] Найдено видео в entities: {video_url}")
                                    break
                            if video_url:
                                break
            
            # 3. Проверяем вложения в attachments
            if not video_url and not photo_urls:
                attachments = tweet.get('attachments', {})
                if attachments:
                    print("[DEBUG] Проверяем поле attachments")
                    media_keys = attachments.get('media_keys', [])
                    included_media = tweet_data.get('includes', {}).get('media', [])
                    if included_media:
                        print(f"[DEBUG] Найдено {len(included_media)} медиа в includes")
                        for media_item in included_media:
                            media_key = media_item.get('media_key')
                            if media_key in media_keys:
                                media_type = media_item.get('type')
                                print(f"[DEBUG] Тип медиа в includes: {media_type}")
                                
                                # Проверяем на фото
                                if media_type == 'photo':
                                    photo_url = media_item.get('url')
                                    if photo_url:
                                        photo_urls.append(photo_url)
                                        print(f"[DEBUG] Найдено фото в includes: {photo_url}")
                                
                                # Проверяем на видео
                                elif media_type == 'video' or media_type == 'animated_gif':
                                    variants = media_item.get('variants', [])
                                    for variant in variants:
                                        if variant.get('content_type') == 'video/mp4':
                                            video_url = variant.get('url')
                                            print(f"[DEBUG] Найдено видео в includes: {video_url}")
                                            break
                                    # Проверяем видео в URL
                                    if not video_url and media_item.get('url'):
                                        video_url = media_item.get('url')
                                        print(f"[DEBUG] Найдено видео URL в includes: {video_url}")
                                if video_url:
                                    break
            
            # 4. Если медиа все еще не найдено, проверяем ссылки в тексте
            if not video_url and not photo_urls:
                urls = tweet.get('entities', {}).get('urls', [])
                for url_obj in urls:
                    expanded_url = url_obj.get('expanded_url', '')
                    # Проверяем на видео
                    if 'video' in expanded_url or '.mp4' in expanded_url:
                        video_url = expanded_url
                        print(f"[DEBUG] Найдено видео в URL: {video_url}")
                        break
                    # Проверяем на фото
                    elif any(ext in expanded_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        photo_urls.append(expanded_url)
                        print(f"[DEBUG] Найдено фото в URL: {expanded_url}")
            
            # Выводим итоги поиска медиа
            if video_url:
                print(f"[DEBUG] Итоговая ссылка на видео: {video_url}")
            elif photo_urls:
                print(f"[DEBUG] Найдено фото: {len(photo_urls)} шт.")
                for i, url in enumerate(photo_urls):
                    print(f"[DEBUG] Фото #{i+1}: {url}")
            else:
                print("[DEBUG] Медиа не найдено в твите")
            
            # Проверка на ретвит или цитату
            is_quote = tweet.get('isQuote', False)
            is_retweet = tweet.get('isRetweet', False)
            
            # Переменные для медиа в цитируемом твите
            quoted_video_url = None
            quoted_photo_urls = []
            
            if is_quote or is_retweet:
                quoted_tweet = tweet.get('quoted_tweet', {})
                if quoted_tweet:
                    quoted_author = quoted_tweet.get('author', {})
                    quoted_username = quoted_author.get('userName', '')
                    quoted_text = self.clean_text(quoted_tweet.get('text', ''))
                    
                    print(f"[DEBUG] Цитируемый твит от {quoted_username}: {quoted_text[:100]}...")
                    
                    # Поиск медиа в цитируемом твите
                    print("[DEBUG] Ищем медиа в цитируемом твите...")
                    
                    # 1. Проверяем поле extendedEntities в цитируемом твите
                    quoted_extended_entities = quoted_tweet.get('extendedEntities', {})
                    if quoted_extended_entities:
                        print("[DEBUG] Найдено поле extendedEntities в цитируемом твите")
                        quoted_media = quoted_extended_entities.get('media', [])
                        for item in quoted_media:
                            media_type = item.get('type', '')
                            print(f"[DEBUG] Тип медиа в цитируемом твите: {media_type}")
                            
                            # Проверяем на фото
                            if media_type == 'photo':
                                photo_url = item.get('media_url_https')
                                if photo_url:
                                    quoted_photo_urls.append(photo_url)
                                    print(f"[DEBUG] Найдено фото в цитируемом твите: {photo_url}")
                            
                            # Проверяем на видео
                            elif media_type == 'video' or media_type == 'animated_gif':
                                print("[DEBUG] Найдено видео в цитируемом твите")
                                variants = item.get('video_info', {}).get('variants', [])
                                # Сортируем варианты по битрейту
                                sorted_variants = sorted(variants, key=lambda x: x.get('bitrate', 0), reverse=True)
                                for variant in sorted_variants:
                                    content_type = variant.get('content_type', '')
                                    if content_type == 'video/mp4':
                                        quoted_video_url = variant.get('url')
                                        print(f"[DEBUG] Выбран вариант видео MP4 из цитаты: {quoted_video_url}")
                                        break
                                if quoted_video_url:
                                    break
                    
                    # Формируем сообщение для Telegram с жирным шрифтом
                    telegram_message = f'<b>👨🏽‍🦰{self.format_username(username)} сделал ретвит поста {self.format_username(quoted_username)}</b>\n\n'
                    telegram_message += f'<b>✏️Ответ: {text}</b>\n\n'
                    telegram_message += f'<b>🧲 На пост: {quoted_text}</b>'
                    
                    # Формируем сообщение для Discord с жирным шрифтом
                    discord_message = f'**👨🏽‍🦰{self.format_username(username, True)} сделал ретвит поста {self.format_username(quoted_username, True)}**\n\n'
                    discord_message += f'**✏️Ответ: {text}**\n\n'
                    discord_message += f'**🧲 На пост: {quoted_text}**'
                    
                    # Отправляем основное сообщение с медиа
                    print("[DEBUG] Отправляем сообщение о ретвите/цитате")
                    
                    # Приоритет отправки: 
                    # 1. Видео из оригинального твита
                    # 2. Видео из цитируемого твита
                    # 3. Фото из оригинального твита
                    # 4. Фото из цитируемого твита
                    # 5. Только текст
                    
                    if video_url:
                        # Если есть видео в оригинальном твите, отправляем его
                        print("[DEBUG] Отправляем с видео из оригинального твита")
                        result = self.send_message(telegram_message, video_url)
                    elif quoted_video_url:
                        # Если есть видео в цитируемом твите, отправляем его
                        print("[DEBUG] Отправляем с видео из цитируемого твита")
                        result = self.send_message(telegram_message, quoted_video_url)
                    elif photo_urls:
                        # Если есть фото в оригинальном твите, отправляем первое
                        print("[DEBUG] Отправляем с фото из оригинального твита")
                        result = self.send_message(telegram_message, photo_urls[0])
                        
                        # Отправляем дополнительные фото отдельными сообщениями
                        if len(photo_urls) > 1:
                            additional_caption = f"<b>Дополнительные фото из поста {self.format_username(username)}</b>"
                            additional_discord_caption = f"**Дополнительные фото из поста {self.format_username(username, True)}**"
                            
                            for photo_url in photo_urls[1:]:
                                self.send_message(additional_caption, photo_url)
                                # Отдельно отправляем в Discord
                                if self.discord_webhook_url:
                                    self.send_additional_photo_to_discord(additional_discord_caption, photo_url)
                    elif quoted_photo_urls:
                        # Если есть фото в цитируемом твите, отправляем первое
                        print("[DEBUG] Отправляем с фото из цитируемого твита")
                        result = self.send_message(telegram_message, quoted_photo_urls[0])
                        
                        # Отправляем дополнительные фото отдельными сообщениями
                        if len(quoted_photo_urls) > 1:
                            additional_caption = f"<b>Дополнительные фото из цитируемого поста {self.format_username(quoted_username)}</b>"
                            additional_discord_caption = f"**Дополнительные фото из цитируемого поста {self.format_username(quoted_username, True)}**"
                            
                            for photo_url in quoted_photo_urls[1:]:
                                self.send_message(additional_caption, photo_url)
                                # Отдельно отправляем в Discord
                                if self.discord_webhook_url:
                                    self.send_additional_photo_to_discord(additional_discord_caption, photo_url)
                    else:
                        # Если нет медиа, отправляем только текст
                        result = self.send_message(telegram_message)
                    
                    print(f"[DEBUG] Результат отправки: {'успешно' if result else 'ошибка'}")
                    return result
            else:
                # Формируем сообщение для Telegram с жирным шрифтом
                telegram_message = f'<b>👨🏽‍🦰{self.format_username(username)} опубликовал новый твит:</b>\n\n'
                telegram_message += f'<b>✏️{text}</b>'
                
                # Формируем сообщение для Discord с жирным шрифтом
                discord_message = f'**👨🏽‍🦰{self.format_username(username, True)} опубликовал новый твит:**\n\n'
                discord_message += f'**✏️{text}**'
                
                # Отправляем основное сообщение с первым медиа
                print("[DEBUG] Отправляем сообщение о новом твите")
                if video_url:
                    # Если есть видео, отправляем его с текстом
                    result = self.send_message(telegram_message, video_url)
                elif photo_urls:
                    # Если есть фото, отправляем первое с текстом
                    result = self.send_message(telegram_message, photo_urls[0])
                    
                    # Отправляем дополнительные фото отдельными сообщениями
                    if len(photo_urls) > 1:
                        additional_caption = f"<b>Дополнительные фото из поста {self.format_username(username)}</b>"
                        additional_discord_caption = f"**Дополнительные фото из поста {self.format_username(username, True)}**"
                        
                        for photo_url in photo_urls[1:]:
                            self.send_message(additional_caption, photo_url)
                            # Отдельно отправляем в Discord
                            if self.discord_webhook_url:
                                self.send_additional_photo_to_discord(additional_discord_caption, photo_url)
                else:
                    # Если нет медиа, отправляем только текст
                    result = self.send_message(telegram_message)
                
                print(f"[DEBUG] Результат отправки: {'успешно' if result else 'ошибка'}")
                return result
                
        except Exception as e:
            print(f"Ошибка обработки твита: {e}")
            import traceback
            print(traceback.format_exc())
            return False
    
    def process_api_json(self):
        """Process api.json file and send tweets to Telegram"""
        try:
            if not os.path.exists('api.json'):
                print("[DEBUG] Файл api.json не найден")
                return
            
            print("[DEBUG] Читаем файл api.json")
            with open('api.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print("[DEBUG] Очищаем файл api.json после чтения")
            with open('api.json', 'w', encoding='utf-8') as f:
                json.dump([], f)
            
            if not data:
                print("[DEBUG] Данные пусты, нечего обрабатывать")
                return
            
            # Вывод информации о каждом твите в данных
            ids_found = []
            for i, tweet_data in enumerate(data):
                tweets = tweet_data.get('tweets', [])
                if tweets:
                    tweet_id = tweets[0].get('id', 'unknown')
                    ids_found.append(tweet_id)
                    print(f"[DEBUG] Найден твит #{i+1} с ID: {tweet_id}")
            
            # Проверка на дубликаты ID в одном запуске
            unique_ids = set(ids_found)
            if len(unique_ids) != len(ids_found):
                print(f"[ВНИМАНИЕ] Обнаружены дубликаты ID в текущем наборе: {ids_found}")
            
            print(f"[DEBUG] Начинаем обработку {len(data)} твитов")
            
            for i, tweet_data in enumerate(data):
                print(f"[DEBUG] Обрабатываем твит #{i+1}")
                self.process_tweet(tweet_data)
                
        except Exception as e:
            print(f"Ошибка обработки api.json: {e}")
            import traceback
            print(traceback.format_exc())

    async def close(self):
        """Close the bot session"""
        await self.bot.close()

# Example usage:
# bot = TwitterTelegramBot("YOUR_TELEGRAM_BOT_TOKEN", "YOUR_CHAT_ID")
# bot.process_api_json()
# asyncio.run(bot.close()) 
