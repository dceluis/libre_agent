class ChatTool {
  name "ChatTool"
  content string
  parse_mode ParseMode
}

class MemoryCreateTool {
  name "MemoryCreateTool"
  unit_name string
  content string
  priority_level PriorityLevel
  temporal_scope TemporalScope
  role Role
}

class MemoryUpdateTool {
  name "MemoryUpdateTool"
  memory_id string
  content string?
  priority_level PriorityLevel?
  temporal_scope TemporalScope?
}

class MemoryDeleteTool {
  name "MemoryDeleteTool"
  memory_id string
}

enum Role {
  REFLECTION
  EPISODIC
  SEMANTIC
  PROCEDURAL
}

enum ParseMode {
  PLAINTEXT
  MARKDOWN
}

enum PriorityLevel {
  CORE
  HIGH
  MEDIUM
  LOW
  BACKGROUND
}

enum TemporalScope {
  SHORT_TERM
  LONG_TERM
}

function UseTools(content: string) -> (ChatTool | MemoryUpdateTool | MemoryCreateTool | MemoryDeleteTool)[] {
  client Groq
  prompt #"
    {{ content }}

    {{ ctx.output_format }}
  "#
}
