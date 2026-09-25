import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";

import { getToken } from "@/lib/api";

export default function Index() {
  const [checking, setChecking] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
    useEffect(() => {
    getToken().then((token) => {
      setIsLoggedIn(!!token);
      setChecking(false);
    });
  }, []);
    if (checking) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return <Redirect href={isLoggedIn ? "/expense" : "/login"} />;
}