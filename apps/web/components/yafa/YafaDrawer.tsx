"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useYafa } from "./YafaProvider";
import YafaChat from "./YafaChat";
import YafaInput from "./YafaInput";

const MIN_W = 320;
const MIN_H = 420;

/**
 * The one global Yafa drawer (Phase 3 sections 29-33). Closing hides the
 * panel but conversation state lives in YafaProvider - nothing is lost.
 * Desktop gets a drag-resize corner handle; mobile keeps the full-width
 * drawer (resize handle is display:none under the breakpoint).
 */
export default function YafaDrawer() {
  const { isOpen, closeDrawer, toggleDrawer, resetConversation, pageContext } = useYafa();
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const resizeRef = useRef<{
    startX: number;
    startY: number;
    startW: number;
    startH: number;
  } | null>(null);
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const launcherRef = useRef<HTMLButtonElement | null>(null);

  const close = useCallback(() => {
    closeDrawer();
    window.requestAnimationFrame(() => launcherRef.current?.focus());
  }, [closeDrawer]);

  const onResizeStart = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const drawer = drawerRef.current;
      if (!drawer) return;
      event.preventDefault();
      resizeRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        startW: drawer.offsetWidth,
        startH: drawer.offsetHeight,
      };
      drawer.setPointerCapture(event.pointerId);
    },
    [],
  );

  const onResizeMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const start = resizeRef.current;
    if (!start) return;
    const maxWidth = Math.min(window.innerWidth * 0.9, 560);
    const maxHeight = window.innerHeight * 0.92;
    const width = Math.min(maxWidth, Math.max(MIN_W, start.startW + (start.startX - event.clientX)));
    const height = Math.min(maxHeight, Math.max(MIN_H, start.startH + (event.clientY - start.startY)));
    setSize({ width, height });
  }, []);

  const onResizeEnd = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    resizeRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  }, []);

  // Escape closes; focus returns to the launcher so nobody is trapped.
  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, close]);

  const contextLabel = pageContext?.type === "product"
    ? "Guidance for the product you’re viewing"
    : pageContext?.type === "cart"
      ? "Guidance for your bag"
      : pageContext?.type === "category"
        ? "Guidance for this collection"
        : null;

  const inlineSize = size
    ? ({ width: `${size.width}px`, height: `${size.height}px` } as const)
    : undefined;

  return (
    <>
      <button
        type="button"
        className="yafa-fab"
        ref={launcherRef}
        onClick={toggleDrawer}
        aria-expanded={isOpen}
        aria-controls="yafa-drawer"
        aria-label="Open Yafa beauty assistant"
      >
        <span aria-hidden="true">✦</span> Ask YAFA
      </button>

      {isOpen ? (
        <button
          type="button"
          className="yafa-drawer__backdrop"
          onClick={close}
          aria-label="Close Yafa chat"
        />
      ) : null}

      <div
        id="yafa-drawer"
        ref={drawerRef}
        className={`yafa-drawer ${isOpen ? "is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Yafa beauty assistant"
        hidden={!isOpen}
        style={inlineSize}
      >
        <header className="yafa-drawer__header">
          <div className="yafa-drawer__title">
            <h2>Ask Yafa</h2>
            <p>Your personal beauty companion</p>
            {contextLabel ? <span className="yafa-drawer__context">{contextLabel}</span> : null}
          </div>
          <div className="yafa-drawer__actions">
            <button
              type="button"
              className="yafa-drawer__action"
              onClick={resetConversation}
              aria-label="Start a new Yafa conversation"
              title="Start a new conversation"
            >
              <span aria-hidden="true">↻</span>
            </button>
            <button
              type="button"
              className="yafa-drawer__action yafa-drawer__close"
              onClick={close}
              aria-label="Close Yafa chat"
              title="Close"
            >
              <span aria-hidden="true">×</span>
            </button>
          </div>
        </header>

        <YafaChat />

        <div className="yafa-drawer__input">
          <YafaInput />
        </div>

        {/* Desktop-only drag handle (bottom-left corner). */}
        <div
          className="yafa-drawer__resize"
          onPointerDown={onResizeStart}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize chat panel"
        />
      </div>
    </>
  );
}
