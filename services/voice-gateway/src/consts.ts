import { AudioType, AudioMediaType, TextMediaType } from "./types";

/**
 * Yafa configuration. Region/model defaults follow the YAFA AWS direction
 * (us-east-1). Voice is configurable via VOICE_ID env without code changes.
 * Protocol constants are IDENTICAL to the proven AWS sample - do not tweak.
 */

export const YafaConfig = {
  defaultRegion: process.env.AWS_REGION || "us-east-1",
  modelId: process.env.NOVA_SONIC_MODEL_ID || "amazon.nova-2-sonic-v1:0",
  voiceId: process.env.VOICE_ID || "tiffany",
  port: Number(process.env.PORT || 3008),
  host: process.env.HOST || "localhost",
  recommendationServiceUrl: (process.env.YAFA_RECOMMENDATION_SERVICE_URL || "http://localhost:8000").replace(/\/$/, ""),
  internalServiceToken: process.env.YAFA_INTERNAL_SERVICE_TOKEN || "",
  knowledgeTimeoutMs: Math.max(500, Number(process.env.YAFA_KNOWLEDGE_TIMEOUT_MS || 5000)),
  gatewaySigningSecret: process.env.YAFA_VOICE_GATEWAY_SIGNING_SECRET || "",
  gatewayTokenAudience: process.env.YAFA_VOICE_GATEWAY_TOKEN_AUDIENCE || "yafa-voice",
  authRequired: (process.env.YAFA_VOICE_AUTH_REQUIRED || (process.env.NODE_ENV === "production" ? "true" : "false")) === "true",
  maxSessionMs: Math.max(60_000, Number(process.env.YAFA_VOICE_MAX_SESSION_MS || 600_000)),
  maxAudioChunkBytes: Math.max(3_200, Number(process.env.YAFA_VOICE_MAX_AUDIO_CHUNK_BYTES || 65_536)),
  maxTextChars: Math.max(1, Number(process.env.YAFA_VOICE_MAX_TEXT_CHARS || 1000)),
  maxConnectionsPerMinute: Math.max(1, Number(process.env.YAFA_VOICE_MAX_CONNECTIONS_PER_MINUTE || 10)),
  maxConcurrentConnectionsPerUser: Math.max(1, Number(process.env.YAFA_VOICE_MAX_CONNECTIONS_PER_USER || 2)),
  maxTextEventsPerMinute: Math.max(1, Number(process.env.YAFA_VOICE_MAX_TEXT_EVENTS_PER_MINUTE || 20)),
  maxAudioEventsPerMinute: Math.max(60, Number(process.env.YAFA_VOICE_MAX_AUDIO_EVENTS_PER_MINUTE || 720)),
  // Browser origins allowed to open a socket to this gateway.
  allowedOrigins: (process.env.ALLOWED_ORIGINS ||
    "http://localhost:3000,http://127.0.0.1:3000"
  ).split(",").map((origin) => origin.trim()),
};

if (YafaConfig.authRequired && YafaConfig.gatewaySigningSecret.length < 32) {
  throw new Error("YAFA_VOICE_GATEWAY_SIGNING_SECRET must contain at least 32 characters when voice authentication is required");
}

export const DefaultInferenceConfiguration = {
  maxTokens: 1024,
  topP: 0.9,
  temperature: 0.7,
};

export const DefaultAudioInputConfiguration = {
  audioType: "SPEECH" as AudioType,
  encoding: "base64",
  mediaType: "audio/lpcm" as AudioMediaType,
  sampleRateHertz: 16000,
  sampleSizeBits: 16,
  channelCount: 1,
};

export const DefaultTextConfiguration = { mediaType: "text/plain" as TextMediaType };

export const DefaultAudioOutputConfiguration = {
  mediaType: "audio/lpcm" as AudioMediaType,
  sampleRateHertz: 24000,
  sampleSizeBits: 16,
  channelCount: 1,
  voiceId: YafaConfig.voiceId,
  encoding: "base64",
  audioType: "SPEECH" as AudioType,
  bufferMs: 200,
};

export const ToolConfiguration = {
  maxResultLength: 20480,
};
