interface TAMIFloatingButtonProps {
  onClick: () => void;
}

export function TAMIFloatingButton({ onClick }: TAMIFloatingButtonProps) {
  return (
    <button
      onClick={onClick}
      className="
        fixed bottom-6 right-6
        w-14 h-14
        rounded-full
        bg-violet-400 hover:bg-violet-500
        text-white
        shadow-lg hover:shadow-xl
        transition-all duration-200
        hover:scale-105
        flex items-center justify-center
        z-50
      "
      aria-label="Chat with TAMI"
    >
      <span className="text-lg font-semibold">AI</span>
    </button>
  );
}
