import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const glassCardVariants = cva(
  "relative rounded-2xl transition-all duration-300",
  {
    variants: {
      variant: {
        default: "glass shadow-lg shadow-black/5 hover:shadow-xl",
        subtle: "glass-subtle shadow-md shadow-black/5 hover:shadow-lg",
        strong: "glass-strong shadow-lg shadow-black/5 hover:shadow-xl",
        overlay: "glass-overlay shadow-lg shadow-black/5 hover:shadow-xl",
        dark: "glass-dark shadow-lg shadow-black/10 hover:shadow-xl",
        solid: "bg-white/40 backdrop-blur-md border border-white/20 shadow-lg shadow-black/5 hover:shadow-xl",
      },
      glow: {
        true: "glass-glow",
        false: "",
      },
      hover: {
        true: "hover:bg-white/80",
        false: "",
      },
    },
    defaultVariants: {
      variant: "default",
      glow: true,
      hover: true,
    },
  }
)

export interface GlassCardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof glassCardVariants> {}

function GlassCard({
  className,
  variant,
  glow,
  hover,
  children,
  ...props
}: GlassCardProps) {
  return (
    <div
      className={cn(glassCardVariants({ variant, glow, hover }), className)}
      {...props}
    >
      <div className="relative z-10">{children}</div>
    </div>
  )
}

function GlassCardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-1.5 p-5 pb-0", className)}
      {...props}
    />
  )
}

function GlassCardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("font-bold text-lg leading-none tracking-tight", className)}
      {...props}
    />
  )
}

function GlassCardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

function GlassCardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />
}

function GlassCardFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center p-5 pt-0", className)}
      {...props}
    />
  )
}

export {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardDescription,
  GlassCardContent,
  GlassCardFooter,
  glassCardVariants,
}
