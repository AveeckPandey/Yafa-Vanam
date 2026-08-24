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
  // Browser origins allowed to open a socket to this gateway.
  allowedOrigins: (process.env.ALLOWED_ORIGINS ||
    "http://localhost:3000,http://127.0.0.1:3000"
  ).split(",").map((origin) => origin.trim()),
};

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
