import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "default" | "secondary" | "outline" | "ghost" | "destructive" | "success";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const variantClasses: Record<ButtonVariant, string> = {
  default:
    "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:ring-primary",
  secondary:
    "bg-secondary text-secondary-foreground hover:bg-secondary/80 focus-visible:ring-primary",
  outline:
    "border border-border bg-background text-foreground hover:bg-muted focus-visible:ring-primary",
  ghost: "bg-transparent text-foreground hover:bg-muted focus-visible:ring-primary",
  destructive:
    "bg-destructive text-destructive-foreground hover:bg-destructive/90 focus-visible:ring-destructive",
  success:
    "bg-success text-success-foreground hover:bg-success/90 focus-visible:ring-success",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
  icon: "size-10",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
}

export function Button({
  className,
  variant = "default",
  size = "md",
  startIcon,
  endIcon,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full border border-transparent font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {startIcon ? (
        <span aria-hidden="true" data-icon="inline-start" className="inline-flex shrink-0 [&_svg]:size-4">
          {startIcon}
        </span>
      ) : null}
      {children}
      {endIcon ? (
        <span aria-hidden="true" data-icon="inline-end" className="inline-flex shrink-0 [&_svg]:size-4">
          {endIcon}
        </span>
      ) : null}
    </button>
  );
}
