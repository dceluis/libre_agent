# 3. Memory Architecture Evolution

Date: 2024-12-22

## Status

Accepted

## Context

Our current approach to categorizing memory as either “internal” or “external” has been partly driven by privacy considerations and the need to differentiate user inputs/responses from system reflections (e.g., from the Core and Personality Units). However, we have realized that automatically labeling system-generated responses as “external” for chat inclusion introduces confusion, since they are in fact internally produced content—merely user-facing in their final form.

Additionally, any concept of ephemeral memory as a distinct type feels premature. In the future, we may wish to introduce sophisticated memory-forgetting logic or enforce more nuanced visibility rules, neither of which is well-served by having ephemeral as a naive new memory type.

We also note the evolving requirement that reflection trains, even when operating without a live chat interface, still depend on a Working Memory for context. Indeed, to support flexible reflection, chat interactions from all active windows should funnel into a “special” or “global” Working Memory. This ensures that reflection processes (e.g., by the Personality Unit) can remain informed about ongoing user activity, even if those processes remain out of direct user view.

## Decision

1. **Preserve Existing Distinctions While Holding Off on Ephemeral**  
   We will keep the “internal” vs. “external” memory labels for now, acknowledging their limitations. We will not introduce an “ephemeral” type. Future changes—like forgetting, encryption, or partially obfuscated logs—will be addressed with a more robust solution.

2. **Refine Memory Governance**  
   Memory sensitivity or privacy can’t be solved by naive type labels alone. As part of our roadmap, we plan to design a specialized process that regularly prunes or modifies memories based on user-defined or system-defined sensitivity rules, usage frequency, context, and other criteria.

3. **Use a Global Working Memory for Non-Chat Reflection**  
   Reflection processes that occur outside a direct chat flow (e.g., scheduling tasks, sending reminders by email or notifications) will still utilize a dedicated Working Memory. Chat activities from all active sessions may feed into this memory for holistic context.

## Consequences

- **Clarity on “Internal” and “External”**  
  Though not ideal, we retain these types for continuity and easy chat inclusion. We acknowledge that future expansions will likely demand better logic for privacy.

- **Postponed Ephemeral Memory**  
  “Ephemeral” as a type is tabled. Any ephemeral capabilities will come from specialized forgetting/pruning logic, rather than from a distinct memory label.

- **Unified Reflection Context**  
  Reflection across different channels (chat, email, automation) can share a coherent knowledge base, ensuring consistent reasoning about user needs. All chat sessions contribute to a single reflection memory, or a small set of memory pools, as needed.
