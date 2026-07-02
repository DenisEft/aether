from typing import Optional, Any, List, Dict, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.ai import Intent
from app.models.documents import Template, Document
from app.services.document_service import DocumentService


class IntentClassificationService:
    """Classify incoming messages into document intents using keyword matching."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def classify(
        self, text: str, tenant_id: UUID
    ) -> tuple[Optional[Intent], Optional[Template], float]:
        """
        1. Load all active intents for tenant + system intents
        2. Simple keyword match: intent.display_name + intent.name as keywords
        3. If intent found → find matching active template by intent category
        4. Return (intent, template, confidence_score)
        """
        # Normalize text: lowercase, strip punctuation
        normalized_text = text.lower().strip('.,!?;:"()[]{}')
        
        # Load all intents for tenant + system intents
        stmt = select(Intent).where(
            (Intent.tenant_id == tenant_id) | (Intent.tenant_id.is_(None))
        )
        intents = await self._session.execute(stmt)
        intents = intents.scalars().all()
        
        best_intent = None
        best_template = None
        best_score = 0.0
        
        # For each intent, compute score based on keyword matching
        for intent in intents:
            # Create keywords from intent display_name and name
            keywords = []
            if intent.display_name:
                keywords.append(intent.display_name.lower())
            if intent.name:
                keywords.append(intent.name.lower())
            
            # Compute score as longest matching keyword length / text length
            max_match_length = 0
            for keyword in keywords:
                if keyword in normalized_text:
                    match_length = len(keyword)
                    if match_length > max_match_length:
                        max_match_length = match_length
            
            if max_match_length > 0:
                score = max_match_length / len(normalized_text) if len(normalized_text) > 0 else 0
                if score > best_score and score > 0.05:
                    best_score = score
                    best_intent = intent
                    
                    # Find matching template for this intent's category
                    template_stmt = select(Template).where(
                        Template.document_type == intent.category,
                        Template.is_active == True,
                        (Template.tenant_id == tenant_id) | (Template.tenant_id.is_(None))
                    )
                    template_result = await self._session.execute(template_stmt)
                    template = template_result.scalars().first()
                    best_template = template
        
        return (best_intent, best_template, best_score)


class EntityExtractionService:
    """Extract entities from text using regex patterns defined in template fields."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def extract(
        self, text: str, template: Template
    ) -> dict[str, Any]:
        """
        For each field in template.fields that has a 'pattern' key:
        - Apply regex pattern against text
        - Extract matched value
        - Cast to type (number → float, boolean → bool, date → str)
        - Return dict of {field_key: extracted_value}
        
        Built-in extractors (applied regardless of patterns):
        - Email: r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        - Phone: r'\+?[78][- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}'
        - Date: r'\d{2}[./-]\d{2}[./-]\d{2,4}'
        - Money: r'\d+[\s]*(?:руб|₽|RUB|USD|EUR)\b'
        - Cargo weight: r'\d+[\s]*(?:тн|тонн|кг|MT)\b'
        - Wagon number: r'\d{8}' (8-digit number)
        - Order number: r'(?:заказ|заявк|order)[\s№#]*(\d+)'
        - INN: r'\d{10,12}'
        """
        import re
        
        extracted_fields = {}
        
        # Built-in extractors (applied regardless of patterns)
        # Email
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_match = re.search(email_pattern, text)
        if email_match:
            extracted_fields['email'] = email_match.group()
        
        # Phone
        phone_pattern = r'\+?[78][- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            extracted_fields['phone'] = phone_match.group()
        
        # Date
        date_pattern = r'\d{2}[./-]\d{2}[./-]\d{2,4}'
        date_match = re.search(date_pattern, text)
        if date_match:
            extracted_fields['date'] = date_match.group()
        
        # Money
        money_pattern = r'\d+[\s]*(?:руб|₽|RUB|USD|EUR)\b'
        money_match = re.search(money_pattern, text)
        if money_match:
            extracted_fields['money'] = money_match.group()
        
        # Cargo weight
        weight_pattern = r'\d+[\s]*(?:тн|тонн|кг|MT)\b'
        weight_match = re.search(weight_pattern, text)
        if weight_match:
            extracted_fields['weight'] = weight_match.group()
        
        # Wagon number
        wagon_pattern = r'\d{8}'
        wagon_match = re.search(wagon_pattern, text)
        if wagon_match:
            extracted_fields['wagon_number'] = wagon_match.group()
        
        # Order number
        order_pattern = r'(?:заказ|заявк|order)[\s№#]*(\d+)'
        order_match = re.search(order_pattern, text)
        if order_match:
            extracted_fields['order_number'] = order_match.group(1)
        
        # INN
        inn_pattern = r'\d{10,12}'
        inn_match = re.search(inn_pattern, text)
        if inn_match:
            extracted_fields['inn'] = inn_match.group()
        
        # Extract using template patterns
        if template and template.fields:
            for field in template.fields:
                if 'pattern' in field and field['pattern']:
                    pattern = field['pattern']
                    match = re.search(pattern, text)
                    if match:
                        field_key = field['key']
                        value = match.group(1) if match.lastindex else match.group()
                        # Try to cast to appropriate type
                        try:
                            if field.get('type') == 'number':
                                value = float(value)
                            elif field.get('type') == 'boolean':
                                value = bool(value)
                        except (ValueError, TypeError):
                            pass
                        extracted_fields[field_key] = value
        
        return extracted_fields


class AIDocumentPipeline:
    """End-to-end pipeline: message → classified → extracted → document."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
        self._classifier = IntentClassificationService(session)
        self._extractor = EntityExtractionService(session)
        self._documents = DocumentService(session)
    
    async def process_message(
        self,
        text: str,
        tenant_id: UUID,
        source: str = "manual",
        force_template_id: Optional[UUID] = None,
    ) -> dict:
        """
        1. If force_template_id → skip classification, use that template
        2. Classify intent → get template
        3. Extract entities from text using template field patterns
        4. Create document with extracted fields
        5. Return {document, intent, template, fields, confidence}
        """
        intent = None
        template = None
        confidence = 0.0
        
        # If force_template_id is provided, skip classification
        if force_template_id:
            stmt = select(Template).where(Template.id == force_template_id)
            template_result = await self._session.execute(stmt)
            template = template_result.scalars().first()
        else:
            # Classify intent and get template
            intent, template, confidence = await self._classifier.classify(text, tenant_id)
        
        if not template:
            # No template found, return empty result
            return {
                "document": None,
                "intent": intent,
                "template": template,
                "fields": {},
                "confidence": confidence
            }
        
        # Extract entities from text using template field patterns
        fields = await self._extractor.extract(text, template)
        
        # Create document with extracted fields
        from app.services.document_service import DocumentCreate
        
        doc_data = DocumentCreate(
            tenant_id=tenant_id,
            type=template.document_type,
            title=intent.display_name if intent else None,
            fields=fields,
            source=source,
        )
        document = await self._documents.create(doc_data)
        
        return {
            "document": document,
            "intent": intent,
            "template": template,
            "fields": fields,
            "confidence": confidence
        }