export type LLMConfig = {
  llm_link: string;
  personality_statement: string;
  description: string;
  system_prompts: string[];
  disallowed_topics: string[];
};
