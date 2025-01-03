# 2. World State Awareness Enhancement

Date: 2024-12-22

## Status

Accepted

## Context

Integrating world-state awareness into the system is essential for enhancing context and decision-making. Units need to be aware of the current time to make informed decisions based on temporal constraints, scheduling, and other time-sensitive factors.

## Decision

1. **Append World State to System Prompts**: Instead of storing the current time as a memory, the system will append a "World State" section containing the current time to all system prompts. This ensures that units have access to the latest time information without cluttering the memory graph.

2. **Modular Design for Future Enhancements**: The system will be designed to allow dynamic inclusion of additional world-state information (e.g., location, system environment) as needed. Users or configurations can specify which world-state data should be appended to prompts in the future.

## Consequences

- **Memory Efficiency**: By not storing transient world-state data in the memory graph, we maintain a cleaner and more relevant memory structure.

- **Consistent Contextual Information**: Units will consistently receive up-to-date world-state information appended to their prompts, enhancing their decision-making processes.

- **Scalability**: The modular approach allows for easy extension of world-state data without significant architectural changes.
