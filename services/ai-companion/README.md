# YAFA VANAM AI Companion — future service

This is a planned orchestration layer for the conversational beauty companion. It is intentionally not wired into production yet.

Future responsibilities:

1. Run the conversational quiz one question at a time.
2. Optionally accept a user photo for cosmetic skin-tone/undertone and visible-appearance signals (not medical diagnosis).
3. Build the internal profile used by the recommendation engine.
4. Request ranked products/kits from the Python recommendation engine.
5. Use the RAG assistant for grounded product, ingredient, policy, and FAQ explanations.
6. Present exactly three curated kit concepts and a conversational kit reveal.
7. Keep user-facing language voice-ready for future TTS integration.

The current system prompt is stored in `prompts/yafa_vanam_system_prompt.md`.
