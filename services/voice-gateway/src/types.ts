/** Shared types. Adapted from the AWS nova-sonic sample (Apache-2.0). */

export type AudioType = "SPEECH" | "EVENT";
export type AudioMediaType = "audio/lpcm" | "audio/mulaw" | "audio/pcm";
export type TextMediaType = "text/plain";

export interface InferenceConfig {
  maxTokens: number;
  topP: number;
  temperature: number;
}

export type EndpointingSensitivity = "high" | "medium" | "low";

export interface TurnDetectionConfig {
  endpointingSensitivity?: EndpointingSensitivity;
}

export interface ToolChoice {
  auto?: Record<string, never>;
  any?: Record<string, never>;
  tool?: { name: string };
}
