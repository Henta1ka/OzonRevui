"""Auto response generation service"""
import logging
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)


class AutoResponseService:
    """Service for generating automatic responses to reviews"""
    
    def __init__(self):
        pass
    
    async def generate_response(
        self, 
        review_text: str, 
        tone: str = None, 
        prompt_template: str = None,
        signature: str = None
    ) -> dict:
        """
        Generate an automatic response to a review
        
        Args:
            review_text: The review text to respond to
            tone: Response tone (friendly, official, formal)
            prompt_template: Custom prompt template
            signature: Signature to append to response
            
        Returns:
            {
                "text": str,
                "is_generated": bool,
                "mode": "ai" | "fallback",
                "error": str or null
            }
        """
        
        # Use defaults from config if not provided
        tone = tone or getattr(settings, 'response_tone', 'friendly')
        prompt_template = prompt_template or getattr(settings, 'response_prompt', self._get_default_prompt(tone))
        signature = signature or getattr(settings, 'response_signature', '')
        
        # Build the full prompt
        full_prompt = self._build_prompt(review_text, tone, prompt_template)
        
        logger.info(f"Generating response for review: {review_text[:50]}...")
        
        # Try to generate via OpenAI
        api_key = getattr(settings, 'openai_api_key', '')
        if api_key and not api_key.startswith('sk-demo-'):
            try:
                from openai import OpenAI
                
                client = OpenAI(api_key=api_key)
                
                # Call OpenAI API directly
                response = client.chat.completions.create(
                    model=getattr(settings, 'openai_model', 'gpt-3.5-turbo'),
                    messages=[
                        {"role": "system", "content": prompt_template},
                        {"role": "user", "content": f"Отзыв:\n\n{review_text}\n\nПожалуйста, напишите профессиональный ответ в тоне: {tone}"}
                    ],
                    temperature=0.7,
                    max_tokens=300,
                    timeout=10
                )
                
                generated_text = response.choices[0].message.content.strip()
                
                # Append signature
                if signature:
                    generated_text = f"{generated_text}\n\n{signature}"
                
                logger.info(f"✅ Generated response via OpenAI API (model: {response.model})")
                return {
                    "text": generated_text,
                    "is_generated": True,
                    "mode": "ai",
                    "error": None
                }
                
            except Exception as e:
                logger.warning(f"Failed to generate via OpenAI: {type(e).__name__}: {str(e)}")
        
        # Fallback mode - generate mock but realistic response
        fallback_response = self._generate_fallback_response(review_text, tone)
        if signature:
            fallback_response = f"{fallback_response}\n\n{signature}"
        
        logger.info(f"Generated response in fallback mode")
        return {
            "text": fallback_response,
            "is_generated": True,
            "mode": "fallback",
            "error": None if not api_key else "AI API not available - using fallback mode"
        }
    
    def _build_prompt(self, review_text: str, tone: str, prompt_template: str) -> str:
        """Build the full prompt for OpenAI"""
        if prompt_template and prompt_template.strip():
            return prompt_template
        return self._get_default_prompt(tone)
    
    def _get_default_prompt(self, tone: str) -> str:
        """Get default prompt template based on tone"""
        prompts = {
            'friendly': 'Вы - вежливый и дружелюбный представитель компании, отвечающий на отзывы покупателей. Ваша цель - выразить благодарность, показать, что вы цените мнение клиента, и предложить помощь.',
            'official': 'Вы - официальный представитель компании. Ваш ответ должен быть профессиональным, информативным и содержать конкретные решения проблем.',
            'formal': 'Вы - руководитель компании. Ваш ответ должен быть формальным, серьезным и содержать гарантии качества.'
        }
        return prompts.get(tone, prompts['friendly'])
    
    def _generate_fallback_response(self, review_text: str, tone: str) -> str:
        """Generate a mock response when API is not available"""
        
        # Detect if review is positive, neutral, or negative
        negative_words = ['плохо', 'ужас', 'ужасно', 'не работает', 'сломан', 'разочаров', 'хлам', 'брак', 'дефект']
        positive_words = ['спасибо', 'отлично', 'хороший', 'хорошо', 'прекрасно', 'люблю', 'нравится', 'отличное']
        
        review_lower = review_text.lower()
        is_negative = any(word in review_lower for word in negative_words)
        is_positive = any(word in review_lower for word in positive_words)
        
        # Generate response based on tone and sentiment
        if tone == 'friendly':
            if is_negative:
                return "Спасибо за обратную связь! 😔 Нам жаль, что вы остались недовольны. Это не соответствует нашим стандартам качества. Пожалуйста, свяжитесь с нашей службой поддержки, и мы обязательно разберемся в проблеме и найдем решение. Ваше удовлетворение для нас очень важно! 💙"
            else:
                return "Спасибо за ваш отзыв! 😊 Мы очень рады, что вам понравился наш товар! Ваше мнение помогает нам улучшать качество обслуживания. Надеемся на долгое сотрудничество! 🙌"
        
        elif tone == 'official':
            if is_negative:
                return "Уважаемый клиент! Благодарим вас за оставленный отзыв. Мы принимаем критику серьезно и проведем внутреннее расследование указанной проблемы. Наша служба поддержки свяжется с вами для детального разбора ситуации и поиска оптимального решения. Ваше доверие важно для нас."
            else:
                return "Спасибо за положительную оценку! Мы ценим вашу лояльность и будем продолжать предоставлять высокое качество товаров и услуг. При возникновении любых вопросов наша служба поддержки готова помочь."
        
        else:  # formal
            if is_negative:
                return "Уважаемый клиент! Глубоко сожалеем о возникшей ситуации. Компания гарантирует качество всей продукции и обслуживания. Просим вас связаться с нашей дирекцией для немедленного рассмотрения и восстановления справедливости. Мы готовы предложить полное возмещение убытков."
            else:
                return "Уважаемый клиент! Выражаем признательность за высокую оценку нашей работы. Ваше удовлетворение - главная цель нашей деятельности. Компания гарантирует постоянное совершенствование качества. Будем рады видеть вас среди постоянных клиентов."
