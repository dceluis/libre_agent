// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview


client<llm> Gemini {
  provider google-ai
  options {
    api_key env.GEMINI_API_KEY
    model "gemini-2.0-flash-thinking-exp-01-21"
  }
}

client<llm> Gemini2Flash {
  provider google-ai
  options {
    api_key env.GEMINI_API_KEY
    model "gemini-2.0-flash"
  }
}

client<llm> Fallback70 {
  provider fallback
  options {
    strategy [Openrouter70, Groq70]
  }
}

client<llm> Openrouter70 {
  provider "openai-generic"
  options {
    base_url "https://openrouter.ai/api/v1"
    api_key env.OPENROUTER_API_KEY
    model "deepseek/deepseek-r1-distill-llama-70b"
    headers {
      "HTTP-Referer" "YOUR-SITE-URL" // Optional
      "X-Title" "YOUR-TITLE" // Optional
    }
  }
}

client<llm> Openrouter32 {
  provider "openai-generic"
  options {
    base_url "https://openrouter.ai/api/v1"
    api_key env.OPENROUTER_API_KEY
    model "deepseek/deepseek-r1-distill-qwen-32b"
    headers {
      "HTTP-Referer" "YOUR-SITE-URL" // Optional
      "X-Title" "YOUR-TITLE" // Optional
    }
  }
}

client<llm> Huggingface {
  provider openai-generic
  options {
    base_url "https://api-inference.huggingface.co/v1"
    api_key env.HUGGINGFACE_API_KEY
    model "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
  }
}

client<llm> Groq70 {
  provider openai-generic
  options {
    base_url "https://api.groq.com/openai/v1"
    api_key env.GROQ_API_KEY
    model "deepseek-r1-distill-llama-70b"
  }
}

client<llm> CustomGPT4oMini {
  provider openai
  retry_policy Exponential
  options {
    model "gpt-4o-mini"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> CustomSonnet {
  provider anthropic
  options {
    model "claude-3-5-sonnet-20241022"
    api_key env.ANTHROPIC_API_KEY
  }
}

client<llm> CustomHaiku {
  provider anthropic
  retry_policy Constant
  options {
    model "claude-3-haiku-20240307"
    api_key env.ANTHROPIC_API_KEY
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/round-robin
client<llm> CustomFast {
  provider round-robin
  options {
    // This will alternate between the two clients
    strategy [CustomGPT4oMini, CustomHaiku]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/retry
retry_policy Constant {
  max_retries 3
  // Strategy is optional
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  // Strategy is optional
  strategy {
    type exponential_backoff
    delay_ms 300
    mutliplier 1.5
    max_delay_ms 10000
  }
}
