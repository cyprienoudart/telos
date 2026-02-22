"use client";

import { useState } from "react";
import VideoIntro from "@/components/VideoIntro";
import WelcomeSplash from "@/components/WelcomeSplash";
import ChatApp from "@/components/ChatApp";

type Phase = "video" | "welcome" | "chat";

export default function Home() {
  const [phase, setPhase] = useState<Phase>("video");

  return (
    <>
      {phase === "video" && (
        <VideoIntro onComplete={() => setPhase("welcome")} />
      )}
      {phase === "welcome" && (
        <WelcomeSplash onContinue={() => setPhase("chat")} />
      )}
      {phase === "chat" && (
        <div className="chat-fade-in">
          <ChatApp />
        </div>
      )}
    </>
  );
}
