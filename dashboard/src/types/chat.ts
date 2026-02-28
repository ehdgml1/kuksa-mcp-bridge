/**
 * Chat type definitions for the AI assistant panel.
 *
 * Defines TypeScript interfaces for chat messages, tool call
 * information, and the SSE-based agent communication protocol.
 */

/** Unique message identifier. */
export type MessageId = string;

/** Chat message role. */
export type MessageRole = "user" | "assistant";

/** Tool call execution status. */
export type ToolCallStatus = "calling" | "done" | "error";

/** Agent server event type. */
export type AgentEventType =
  | "tool_call"
  | "tool_result"
  | "text_chunk"
  | "error"
  | "done";

/** Information about a tool invocation within a message. */
export interface ToolCallInfo {
  readonly name: string;
  readonly args: Record<string, unknown>;
  readonly result?: string;
  readonly status: ToolCallStatus;
}

/** A single chat message (user or assistant). */
export interface ChatMessage {
  readonly id: MessageId;
  readonly role: MessageRole;
  readonly content: string;
  readonly toolCalls?: ToolCallInfo[];
  readonly timestamp: Date;
}

/** Server-sent event from the agent API. */
export interface AgentEvent {
  readonly type: AgentEventType;
  readonly name?: string;
  readonly args?: Record<string, unknown>;
  readonly result?: string;
  readonly content?: string;
  readonly message?: string;
}

/** History entry sent to the agent API. */
export interface ChatHistoryEntry {
  readonly role: MessageRole;
  readonly content: string;
}
