export type AIProviderName = "groq" | "openai-compatible";

export interface TenantAIProvider {
  id: string;
  provider: string;
  base_url: string | null;
  model: string;
  is_active: boolean;
  api_key_masked: string;
  created_at: string;
  updated_at: string;
}

export interface TenantAIProviderUpsert {
  provider: AIProviderName;
  api_key: string;
  model: string;
  base_url: string | null;
}

export function providerLabel(provider: string): string {
  return provider === "openai-compatible" ? "OpenAI-compatible" : "Groq";
}

export function validateProviderInput(input: {
  provider: AIProviderName;
  apiKey: string;
  model: string;
  baseUrl: string;
}): string | null {
  if (input.apiKey.trim().length < 8) return "API key must contain at least 8 characters.";
  if (!input.model.trim()) return "Model name is required.";
  if (input.provider === "openai-compatible") {
    try {
      const url = new URL(input.baseUrl.trim());
      if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error();
    } catch {
      return "Enter a valid HTTP(S) base URL for the OpenAI-compatible provider.";
    }
  }
  return null;
}
