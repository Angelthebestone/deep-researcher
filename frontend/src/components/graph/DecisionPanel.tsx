"use client";

import { useState, useCallback } from "react";
import {
  Card,
  CardBody,
  Input,
  Textarea,
  Button,
  Select,
  SelectItem,
  Chip,
} from "@nextui-org/react";
import { Gavel, Save, X } from "lucide-react";
import type { GraphNodeData } from "@/components/graph/flow/types";

export type DecisionStatus = "pendiente" | "aprobado" | "rechazado" | "en evaluación";

export interface Decision {
  id: string;
  nodeLabel: string;
  recommendation: string;
  discardedAlternative: string;
  approvedBy: string;
  decisionDate: string;
  status: DecisionStatus;
}

const decisionsByNode = new Map<string, Decision[]>();

export function getNodeDecisions(nodeLabel: string): Decision[] {
  return decisionsByNode.get(nodeLabel) ?? [];
}

export const statusColorMap: Record<DecisionStatus, "default" | "primary" | "secondary" | "success" | "warning" | "danger"> = {
  pendiente: "warning",
  aprobado: "success",
  rechazado: "danger",
  "en evaluación": "primary",
};

interface DecisionPanelProps {
  node: GraphNodeData | null;
  isOpen: boolean;
  onClose: () => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function DecisionPanel({ node, isOpen, onClose }: DecisionPanelProps) {
  const [recommendation, setRecommendation] = useState("");
  const [discardedAlternative, setDiscardedAlternative] = useState("");
  const [approvedBy, setApprovedBy] = useState("");
  const [decisionDate, setDecisionDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [status, setStatus] = useState<DecisionStatus>("pendiente");
  const [decisions, setDecisions] = useState<Decision[]>(() => (node ? getNodeDecisions(node.label) : []));

  const handleSave = useCallback(() => {
    if (!node) return;
    const newDecision: Decision = {
      id: generateId(),
      nodeLabel: node.label,
      recommendation,
      discardedAlternative,
      approvedBy,
      decisionDate,
      status,
    };
    const updated = [...getNodeDecisions(node.label), newDecision];
    decisionsByNode.set(node.label, updated);
    setDecisions(updated);
    setRecommendation("");
    setDiscardedAlternative("");
    setApprovedBy("");
    setDecisionDate(new Date().toISOString().split("T")[0]);
    setStatus("pendiente");
  }, [node, recommendation, discardedAlternative, approvedBy, decisionDate, status]);

  if (!isOpen || !node) return null;

  return (
    <Card className="w-full border-0 shadow-none bg-transparent">
      <CardBody className="p-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
            <Gavel className="size-3.5" />
            Registrar decisión
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1 hover:bg-muted transition-colors"
            aria-label="Cerrar panel"
          >
            <X className="size-4 text-muted-foreground" />
          </button>
        </div>

        <Textarea
          label="¿Por qué se recomienda?"
          value={recommendation}
          onChange={(e) => setRecommendation(e.target.value)}
          minRows={2}
        />
        <Textarea
          label="¿Qué alternativa se descartó?"
          value={discardedAlternative}
          onChange={(e) => setDiscardedAlternative(e.target.value)}
          minRows={2}
        />
        <Input
          label="¿Quién aprobó?"
          value={approvedBy}
          onChange={(e) => setApprovedBy(e.target.value)}
        />
        <Input
          type="date"
          label="Fecha de decisión"
          value={decisionDate}
          onChange={(e) => setDecisionDate(e.target.value)}
        />
        <Select
          label="Estado de decisión"
          selectedKeys={new Set([status])}
          onSelectionChange={(keys) => {
            const vals = Array.from(keys as Set<string>);
            if (vals.length > 0) setStatus(vals[0] as DecisionStatus);
          }}
        >
          <SelectItem key="pendiente">Pendiente</SelectItem>
          <SelectItem key="aprobado">Aprobado</SelectItem>
          <SelectItem key="rechazado">Rechazado</SelectItem>
          <SelectItem key="en evaluación">En evaluación</SelectItem>
        </Select>

        <Button color="primary" onPress={handleSave} startContent={<Save className="size-4" />}>
          Guardar decisión
        </Button>

        {decisions.length > 0 && (
          <div className="flex flex-col gap-2 mt-2">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
              Historial de decisiones
            </div>
            {decisions.map((d) => (
              <Card key={d.id} className="border border-border bg-muted/30">
                <CardBody className="p-3 flex flex-col gap-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">{d.decisionDate}</span>
                    <Chip size="sm" color={statusColorMap[d.status]} variant="flat">
                      {d.status}
                    </Chip>
                  </div>
                  <div className="text-sm font-medium">{d.approvedBy || "Sin aprobador"}</div>
                  {d.recommendation && (
                    <div className="text-sm text-muted-foreground line-clamp-2">{d.recommendation}</div>
                  )}
                  {d.discardedAlternative && (
                    <div className="text-xs text-muted-foreground line-clamp-1">
                      Descartado: {d.discardedAlternative}
                    </div>
                  )}
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
