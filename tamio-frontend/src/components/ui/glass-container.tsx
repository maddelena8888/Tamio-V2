import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const glassContainerVariants = cva(
  "relative rounded-3xl overflow-hidden",
  {
    variants: {
      color: {
        tomato: "bg-gradient-to-br from-tomato via-tomato to-tomato/90 shadow-2xl shadow-tomato/20",
        gunmetal: "bg-gradient-to-br from-gunmetal via-gunmetal to-gunmetal/90 shadow-2xl shadow-gunmetal/20",
        lime: "bg-gradient-to-br from-lime via-lime to-lime/90 shadow-2xl shadow-lime/20",
        "lime-light": "bg-gradient-to-br from-lime/40 via-lime/30 to-lime/20 shadow-xl shadow-lime/10",
        "gunmetal-light": "bg-gradient-to-br from-gunmetal/20 via-gunmetal/15 to-gunmetal/10 shadow-xl shadow-gunmetal/10",
        mimi: "bg-gradient-to-br from-mimi-pink via-mimi-pink to-mimi-pink/90 shadow-2xl shadow-mimi-pink/20",
        neutral: "bg-gradient-to-br from-slate-800 via-slate-800 to-slate-900/90 shadow-2xl shadow-slate-800/20",
      },
      orbs: {
        true: "",
        false: "",
      },
    },
    defaultVariants: {
      color: "tomato",
      orbs: true,
    },
  }
)

export interface GlassContainerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'color'>,
    VariantProps<typeof glassContainerVariants> {}

function GlassContainer({
  className,
  color,
  orbs,
  children,
  ...props
}: GlassContainerProps) {
  return (
    <div
      className={cn(glassContainerVariants({ color }), className)}
      {...props}
    >
      {/* Subtle gradient overlay for depth */}
      <div className="absolute inset-0 bg-gradient-to-tr from-black/5 via-transparent to-white/10 pointer-events-none" />

      {/* Floating orb effects for glass aesthetic */}
      {orbs && (
        <>
          <div className="absolute -top-20 -right-20 w-64 h-64 bg-white/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-32 -left-20 w-80 h-80 bg-black/10 rounded-full blur-3xl pointer-events-none" />
        </>
      )}

      {/* Content wrapper */}
      <div className="relative z-10">{children}</div>
    </div>
  )
}

function GlassContainerContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 md:p-8", className)} {...props} />
}

// Pre-styled overlay card for use inside GlassContainer
function GlassOverlayCard({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative group bg-white/20 backdrop-blur-xl rounded-2xl border border-white/30 shadow-lg shadow-black/5 transition-all duration-300 hover:bg-white/25 hover:shadow-xl",
        className
      )}
      {...props}
    >
      {/* Inner glow effect */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/40 via-transparent to-transparent opacity-50 pointer-events-none" />
      <div className="relative z-10">{children}</div>
    </div>
  )
}

function GlassOverlayCardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />
}

// Nested item inside overlay cards (like scenario rows)
function GlassOverlayItem({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 p-2.5 rounded-xl bg-white/30 backdrop-blur-sm border border-white/40 shadow-sm transition-all duration-200 hover:bg-white/40",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export {
  GlassContainer,
  GlassContainerContent,
  GlassOverlayCard,
  GlassOverlayCardContent,
  GlassOverlayItem,
  glassContainerVariants,
}
