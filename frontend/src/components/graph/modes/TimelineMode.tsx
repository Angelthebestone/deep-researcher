"use client";

import type { ReactNode } from "react";
import { Card, CardBody, CardHeader, Chip, Divider } from "@nextui-org/react";
import { Clock, TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { TechnologyMention } from "@/types/contracts";

interface TimelineModeProps {
  mentions: TechnologyMention[];
}

function mockFirstSeen(name: string): string {
  const base = new Date("2023-01-01");
  base.setDate(base.getDate() + name.length * 7);
  return base.toLocaleDateString("es-ES");
}

function mockVersions(name: string): string[] {
  const count = (name.length % 3) + 2;
  const versions: string[] = [];
  for (let i = 0; i < count; i++) {
    versions.push(`${1 + i}.${i}.${name.length % 10}`);
  }
  return versions;
}

function maturityMeta(confidence: number): { label: string; icon: ReactNode; color: "success" | "warning" | "danger" | "default" } {
  if (confidence > 0.85) return { label: "Madura", icon: <TrendingUp className="size-4" />, color: "success" };
  if (confidence > 0.6) return { label: "Estable", icon: <Minus className="size-4" />, color: "default" };
  if (confidence > 0.4) return { label: "Emergente", icon: <TrendingUp className="size-4" />, color: "warning" };
  return { label: "En declive", icon: <TrendingDown className="size-4" />, color: "danger" };
}

export function TimelineMode({ mentions }: TimelineModeProps) {
  if (mentions.length === 0) {
    return (
      <Card className="m-4">
        <CardBody className="text-center text-muted-foreground">No hay tecnologías para mostrar en la línea de tiempo.</CardBody>
      </Card>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Clock className="size-5 text-primary" />
        <h2 className="text-lg font-semibold">Línea de tiempo de tecnologías</h2>
      </div>
      <div className="space-y-4">
        {mentions.map((m) => {
          const meta = maturityMeta(m.confidence);
          const versions = mockVersions(m.technology_name);
          const firstSeen = mockFirstSeen(m.technology_name);

          return (
            <Card key={m.mention_id} className="border-0 shadow-soft">
              <CardHeader className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Clock className="size-4" />
                  </div>
                  <div>
                    <div className="font-medium">{m.technology_name}</div>
                    <div className="text-xs text-muted-foreground">Primera detección: {firstSeen}</div>
                  </div>
                </div>
                <Chip color={meta.color} variant="flat" size="sm" startContent={meta.icon}>
                  {meta.label}
                </Chip>
              </CardHeader>
              <Divider />
              <CardBody className="px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Historial de versiones (simulado)</div>
                <div className="flex items-center gap-1 overflow-x-auto">
                  {versions.map((v, i) => (
                    <div key={v} className="flex items-center gap-1 shrink-0">
                      <Chip variant="bordered" size="sm">
                        {v}
                      </Chip>
                      {i < versions.length - 1 && <div className="h-px w-4 bg-border shrink-0" />}
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
