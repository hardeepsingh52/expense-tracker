import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, ApiError } from "@/lib/api";


type Option = {
  label: string;
  recommended: boolean;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  options?: Option[];
};

export default function AskScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend(overrideText?: string) {
    const question = (overrideText ?? input).trim();
    if (!question || loading) return;

    const userMessage: Message = {
      id: `${Date.now()}-user`,
      role: "user",
      text: question,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await api.post<{
        answer: string | null;
        options?: Option[];
        conversation_id: number;
      }>("/ask", { question, conversation_id: conversationId });

      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          text: response.answer ?? "Sorry, I couldn't come up with an answer. Try rephrasing.",
          options: response.options,
        },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-error`, role: "assistant", text: message },
      ]);
    } finally {
      setLoading(false);
    }
  }

    function handleNewChat() {
    setMessages([]);
    setConversationId(null);
  }

    return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Ask</Text>
          <Pressable onPress={handleNewChat}>
            <Text style={styles.newChat}>New Chat</Text>
          </Pressable>
        </View>

        <FlatList
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messageList}
                   renderItem={({ item }) => (
            <View>
              <View
                style={[
                  styles.bubble,
                  item.role === "user" ? styles.userBubble : styles.assistantBubble,
                ]}
              >
                <Text
                  style={item.role === "user" ? styles.userText : styles.assistantText}
                >
                  {item.text}
                </Text>
              </View>

              {item.options && item.options.length > 0 && (
                <View style={styles.optionsRow}>
                  {item.options.map((option) => (
                    <Pressable
                      key={option.label}
                      style={[
                        styles.optionButton,
                        option.recommended && styles.optionButtonRecommended,
                      ]}
                      onPress={() => handleSend(option.label)}
                    >
                      <Text
                        style={[
                          styles.optionButtonText,
                          option.recommended && styles.optionButtonTextRecommended,
                        ]}
                      >
                        {option.label}
                        {option.recommended ? " (Recommended)" : ""}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              )}
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>
              Ask something like &quot;how much did I spend on food this year?&quot;
            </Text>
          }
        />
                <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Ask about your expenses..."
            value={input}
            onChangeText={setInput}
            editable={!loading}
            multiline
          />
                  <Pressable
            style={styles.sendButton}
            onPress={() => handleSend()}
            disabled={loading || !input.trim()}
          >
            {loading ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text style={styles.sendButtonText}>Send</Text>
            )}
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );

}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#ffffff",
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#EEEEF0",
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: "bold",
  },
  newChat: {
    color: "#3B82F6",
    fontSize: 14,
  },
  messageList: {
    padding: 16,
    gap: 10,
    flexGrow: 1,
  },
  emptyText: {
    textAlign: "center",
    color: "#8A8F98",
    marginTop: 40,
    paddingHorizontal: 24,
  },
  bubble: {
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: "85%",
  },
  userBubble: {
    backgroundColor: "#3B82F6",
    alignSelf: "flex-end",
  },
  assistantBubble: {
    backgroundColor: "#F0F0F3",
    alignSelf: "flex-start",
  },
  userText: {
    color: "#ffffff",
    fontSize: 15,
  },
  assistantText: {
    color: "#000000",
    fontSize: 15,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: "#EEEEF0",
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#D0D0D5",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: "#3B82F6",
    borderRadius: 20,
    paddingHorizontal: 18,
    paddingVertical: 12,
    justifyContent: "center",
  },
  sendButtonText: {
    color: "#ffffff",
    fontWeight: "600",
  },
    optionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 6,
    marginBottom: 4,
  },
  optionButton: {
    borderWidth: 1,
    borderColor: "#3B82F6",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  optionButtonRecommended: {
    backgroundColor: "#3B82F6",
  },
  optionButtonText: {
    color: "#3B82F6",
    fontSize: 14,
    fontWeight: "500",
  },
  optionButtonTextRecommended: {
    color: "#ffffff",
  },
});