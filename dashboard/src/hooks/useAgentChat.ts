/**
 * React hook for SSE-based communication with the agent server.
 *
 * Manages chat message state, streams assistant responses via
 * server-sent events, and tracks tool call execution status.
 */

import { useCallback, useRef, useState } from "react";
import type {
  AgentEvent,
  ChatHistoryEntry,
  ChatMessage,
  ToolCallInfo,
} from "../types/chat";

/** API base path for the agent server. */
const API_BASE = "/api";

/** Return type of the useAgentChat hook. */
export interface UseAgentChatResult {
  /** Ordered list of chat messages. */
  readonly messages: ChatMessage[];
  /** Whether the assistant is currently streaming a response. */
  readonly isStreaming: boolean;
  /** Last error message, or null if no error. */
  readonly error: string | null;
  /** Send a user message and begin streaming the assistant response. */
  readonly sendMessage: (text: string) => void;
  /** Clear all messages and reset state. */
  readonly clearMessages: () => void;
}

/**
 * Build conversation history from existing messages.
 *
 * Extracts only role and content for the API request,
 * omitting tool call metadata.
 *
 * @param messages - Current chat messages
 * @returns History entries for the API
 */
function buildHistory(messages: readonly ChatMessage[]): ChatHistoryEntry[] {
  return messages
    .filter((msg) => msg.content.length > 0)
    .map((msg) => ({ role: msg.role, content: msg.content }));
}

/**
 * Parse a single SSE data line into an AgentEvent.
 *
 * @param line - Raw SSE line (e.g., "data: {...}")
 * @returns Parsed event or null if the line is not a data line
 */
function parseSSELine(line: string): AgentEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data: ")) return null;

  const jsonStr = trimmed.slice(6);
  if (jsonStr === "[DONE]") return null;

  try {
    return JSON.parse(jsonStr) as AgentEvent;
  } catch {
    return null;
  }
}

/**
 * Hook that connects to the agent server via SSE for chat.
 *
 * Posts user messages to `/api/chat` and streams assistant
 * responses as server-sent events, tracking tool calls and
 * text chunks incrementally.
 *
 * @returns Chat state and control functions
 */
export function useAgentChat(): UseAgentChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (trimmed.length === 0 || isStreaming) return;

      // Abort any in-flight request
      abortRef.current?.abort();

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };

      const assistantId = crypto.randomUUID();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);
      setError(null);

      const history = buildHistory([...messages, userMessage]);
      const controller = new AbortController();
      abortRef.current = controller;

      streamResponse(assistantId, trimmed, history, controller).catch(
        (err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          const msg =
            err instanceof Error ? err.message : "Unknown error occurred";
          setError(msg);
          setIsStreaming(false);
        },
      );
    },
    [isStreaming, messages],
  );

  /**
   * Stream the assistant response from the agent server.
   *
   * @param assistantId - ID of the assistant message being built
   * @param message - User message text
   * @param history - Conversation history
   * @param controller - AbortController for cancellation
   */
  async function streamResponse(
    assistantId: string,
    message: string,
    history: ChatHistoryEntry[],
    controller: AbortController,
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => "Request failed");
      setError(`Server error (${String(response.status)}): ${detail}`);
      setIsStreaming(false);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      setError("No response body received");
      setIsStreaming(false);
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const event = parseSSELine(line);
          if (!event) continue;

          handleAgentEvent(assistantId, event);
        }
      }

      // Process any remaining buffer
      if (buffer.trim().length > 0) {
        const event = parseSSELine(buffer);
        if (event) {
          handleAgentEvent(assistantId, event);
        }
      }
    } finally {
      reader.releaseLock();
      setIsStreaming(false);
    }
  }

  /**
   * Apply a single agent event to the assistant message state.
   *
   * @param assistantId - Target assistant message ID
   * @param event - Parsed agent event
   */
  function handleAgentEvent(assistantId: string, event: AgentEvent): void {
    switch (event.type) {
      case "tool_call": {
        const toolCall: ToolCallInfo = {
          name: event.name ?? "unknown",
          args: event.args ?? {},
          status: "calling",
        };
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? {
                  ...msg,
                  toolCalls: [...(msg.toolCalls ?? []), toolCall],
                }
              : msg,
          ),
        );
        break;
      }

      case "tool_result": {
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id !== assistantId) return msg;
            const calls = [...(msg.toolCalls ?? [])];
            // Update the most recent tool call with matching name
            for (let i = calls.length - 1; i >= 0; i--) {
              const call = calls[i];
              if (call && call.name === event.name && call.status === "calling") {
                calls[i] = {
                  ...call,
                  result: event.result ?? "",
                  status: "done",
                };
                break;
              }
            }
            return { ...msg, toolCalls: calls };
          }),
        );
        break;
      }

      case "text_chunk": {
        const chunk = event.content ?? "";
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? { ...msg, content: msg.content + chunk }
              : msg,
          ),
        );
        break;
      }

      case "error": {
        setError(event.message ?? "Agent error");
        setIsStreaming(false);
        break;
      }

      case "done": {
        setIsStreaming(false);
        break;
      }
    }
  }

  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, error, sendMessage, clearMessages };
}
