# ElevenLabs voice kit advisor

The Build My Kit page has an optional voice interface. It uses an ElevenLabs **client tool** named `build_personal_kit` to pass a structured kit brief back to the storefront. The storefront sends those preferences to the existing FastAPI advisor, which ranks the final kit from the product catalogue.

## Storefront configuration

1. Create an ElevenLabs Conversational AI agent and make it available for web use.
2. Copy its public agent ID into `apps/web/.env.local`:

   ```env
   NEXT_PUBLIC_ELEVENLABS_AGENT_ID=agent_xxx
   ```

3. In the agent dashboard, add a **Client Tool** named `build_personal_kit`. Turn on blocking so the agent waits for the kit to be rendered.
4. Add these optional string parameters, constrained to the listed values:

   - `goal`: `everyday`, `glow`, `occasion`
   - `finish`: `natural`, `radiant`, `velvet`
   - `focus`: `face`, `colour`, `care`
   - `budget`: `essential`, `complete`, `both`

5. Add the prompt below to the agent.

## Agent prompt

```text
You are YAFA, the warm, concise beauty advisor for YAFA VANAM cosmetics.
Ask one question at a time to understand the customer's desired occasion, finish, product focus, and kit size. Explain that a selfie is optional, ask for consent before requesting one, and never infer sensitive skin or health traits from a photo.

Map the answers to these exact values:
- goal: everyday, glow, or occasion
- finish: natural, radiant, or velvet
- focus: face, colour, or care
- budget: essential, complete, or both

When you have enough information, call build_personal_kit with the collected values. Do not claim a product is in stock, and do not invent product details. After the tool responds, tell the customer their kit is ready to view on the page.
```

## Photos and recommendations

ElevenLabs can request a photo through a separate client tool or a secure webhook, but it should only be uploaded after clear user consent. The current product advisor already has an optional selfie/image-analysis route; connect that route only after configuring a suitable vision provider. Keep the ElevenLabs API key on a server if you later use authenticated agents or signed conversation URLs—do not expose it through `NEXT_PUBLIC_` variables.
