import { useRouter } from "expo-router";
import { Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { clearToken } from "@/lib/api";

export default function ExpenseScreen() {
  const router = useRouter();

  async function handleLogout() {
    await clearToken();
    router.replace("/login");
  }
   return (
    <SafeAreaView style={{ flex: 1 }}>
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 16 }}>
        <Text>Expenses screen — coming soon</Text>

        <Pressable onPress={handleLogout}>
          <Text style={{ color: "#3B82F6" }}>Log out</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}