# AI Module Refactoring Plan

## Current State
- Lines: 810
- Endpoints: 33
- Domains identified: 5

## Proposed Split
| New Module | Endpoints | Lines | Priority |
|--------|---------|-----|--------------|
| intents | list_intents, create_intent, get_intent, update_intent, delete_intent, list_intent_templates, create_intent_template, delete_intent_template | 197 | High |
| entities | list_entity_types, create_entity_type, get_entity_type, update_entity_type, delete_entity_type | 188 | High |
| models | list_ai_models, create_ai_model, update_ai_model, delete_ai_model | 106 | Medium |
| drivers | list_drivers, create_driver, get_driver, update_driver, delete_driver, get_driver_metrics | 134 | High |
| knowledge_bases | list_knowledge_bases, create_knowledge_base, get_knowledge_base, update_knowledge_base, delete_knowledge_base, list_knowledge_documents, create_knowledge_document, delete_knowledge_document | 185 | High |

## Code Smells
| Line | Issue | Fix |
|--------|---------|-----|
| 55-97 | list_intents function is 43 lines long | Split into smaller functions |
| 116-150 | update_intent function is 35 lines long | Split into smaller functions |
| 238-274 | list_entity_types function is 37 lines long | Split into smaller functions |
| 293-327 | update_entity_type function is 35 lines long | Split into smaller functions |
| 353-393 | list_ai_models function is 41 lines long | Split into smaller functions |
| 393-426 | update_ai_model function is 34 lines long | Split into smaller functions |
| 449-495 | list_drivers function is 47 lines long | Split into smaller functions |
| 495-524 | update_driver function is 29 lines long | Split into smaller functions |
| 545-566 | get_driver_metrics function is 22 lines long | Could be simplified |
| 566-600 | list_knowledge_bases function is 35 lines long | Split into smaller functions |
| 600-619 | update_knowledge_base function is 20 lines long | Could be simplified |
| 619-653 | delete_knowledge_base function is 35 lines long | Split into smaller functions |
| 677-723 | list_knowledge_documents function is 47 lines long | Split into smaller functions |
| 723-764 | create_knowledge_document function is 42 lines long | Split into smaller functions |
| 764-806 | run_inference function is 43 lines long | Split into smaller functions |

## Migration Plan
1. Phase 1: Create new modules for each domain (intents, entities, models, drivers, knowledge_bases) under backend/app/api/v1/ai/
2. Phase 2: Move corresponding functions and related code to new modules
3. Phase 3: Update imports and references in the main ai.py file
4. Phase 4: Refactor long functions in new modules to improve maintainability
5. Phase 5: Remove old endpoints from the main ai.py file
