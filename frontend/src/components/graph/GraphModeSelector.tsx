"use client";

import { Button } from "@nextui-org/react";
import { Network, ArrowRightLeft, Clock } from "lucide-react";

export type GraphMode = "technologies" | "comparator" | "timeline";

interface GraphModeSelectorProps {
  mode: GraphMode;
  onModeChange: (mode: GraphMode) => void;
}

const MODES: { key: GraphMode; label: string; icon: React.ReactNode }[] = [
  { key: "technologies", label: "Tecnologías", icon: <Network className="size-4" /> },
  { key: "comparator", label: "Comparador", icon: <ArrowRightLeft className="size-4" /> },
  { key: "timeline", label: "Timeline", icon: <Clock className="size-4" /> },
];

export function GraphModeSelector({ mode, onModeChange }: GraphModeSelectorProps) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-default-100 p-1 shadow-soft">
      {MODES.map((m) => (
        <Button
          key={m.key}
          size="sm"
          radius="full"
          variant={mode === m.key ? "solid" : "light"}
          color={mode === m.key ? "primary" : "default"}
          onPress={() => onModeChange(m.key)}
          startContent={m.icon}
        >
          {m.label}
        </Button>
      ))}
    </div>
  );
}
