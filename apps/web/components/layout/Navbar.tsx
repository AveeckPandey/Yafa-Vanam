"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type FocusEvent,
} from "react";
import AnnouncementBar from "./AnnouncementBar";
import HeaderSearch from "./HeaderSearch";
import MegaMenu, { type MegaMenuKey } from "./MegaMenu";
import MobileMenu from "./MobileMenu";
import { useAuth } from "@/components/auth/AuthProvider";

type MenuTrigger = {
  label: string;
  key: MegaMenuKey;
};

const menuTriggers: MenuTrigger[] = [
  { label: "Skin Care", key: "skincare" },
  { label: "Make Up", key: "makeup" },
  { label: "Body Care", key: "body" },
  { label: "Fragrance", key: "fragrance" },
];

function Wordmark() {
  return (
    <span className="wordmark" aria-hidden="true">
      <span>YAFA</span>
      <span>VANAM</span>
    </span>
  );
}

function ActionIcon({ type }: { type: "search" | "account" | "bag" }) {
  return <span className={`ui-icon ui-icon--${type}`} aria-hidden="true" />;
}

export default function Navbar() {
  const pathname = usePathname();
  const headerRef = useRef<HTMLElement>(null);
  const mobileButtonRef = useRef<HTMLButtonElement>(null);
  const searchTriggerRef = useRef<HTMLButtonElement>(null);
  const [activeMenu, setActiveMenu] = useState<MegaMenuKey | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [bagCount, setBagCount] = useState(0);
  const { isAuthenticated, isLoading, openAuth, logout } = useAuth();

  const closeDesktopMenu = useCallback(() => setActiveMenu(null), []);

  // Hover-intent: sweeping the pointer across the nav must not flash every
  // panel, so pointer entry only schedules an open.
  const hoverTimer = useRef<number | null>(null);
  const cancelScheduledMenu = useCallback(() => {
    if (hoverTimer.current !== null) {
      window.clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  }, []);

  const scheduleOpenMenu = useCallback(
    (menu: MegaMenuKey) => {
      cancelScheduledMenu();
      hoverTimer.current = window.setTimeout(() => {
        hoverTimer.current = null;
        setSearchOpen(false);
        setActiveMenu(menu);
      }, 140);
    },
    [cancelScheduledMenu],
  );

  useEffect(() => cancelScheduledMenu, [cancelScheduledMenu]);

  const openMegaMenu = useCallback(
    (menu: MegaMenuKey) => {
      cancelScheduledMenu();
      setSearchOpen(false);
      setActiveMenu(menu);
    },
    [cancelScheduledMenu],
  );

  // Clicking the visible trigger toggles its panel instead of always reopening.
  const toggleMegaMenu = useCallback(
    (menu: MegaMenuKey) => {
      cancelScheduledMenu();
      setSearchOpen(false);
      setActiveMenu((current) => (current === menu ? null : menu));
    },
    [cancelScheduledMenu],
  );

  // Escape and the panel’s close control hand focus back to the search icon.
  const closeSearch = useCallback(() => {
    setSearchOpen(false);
    window.requestAnimationFrame(() => searchTriggerRef.current?.focus());
  }, []);

  // Outside clicks and route changes dismiss the panel without stealing focus.
  const dismissSearch = useCallback(() => setSearchOpen(false), []);

  const openSearch = useCallback((trigger: HTMLButtonElement) => {
    searchTriggerRef.current = trigger;
    setActiveMenu(null);
    setMobileOpen(false);
    setSearchOpen(true);
  }, []);

  const focusFirstMenuLink = useCallback((menu: MegaMenuKey) => {
    openMegaMenu(menu);
    window.requestAnimationFrame(() => {
      document.querySelector<HTMLAnchorElement>("#desktop-mega-menu a")?.focus();
    });
  }, [openMegaMenu]);

  const handleTriggerKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    menu: MegaMenuKey,
  ) => {
    if (event.key !== "ArrowDown" && event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    focusFirstMenuLink(menu);
  };

  const closeMobileMenu = useCallback(() => {
    setMobileOpen(false);
    window.requestAnimationFrame(() => mobileButtonRef.current?.focus());
  }, []);

  useEffect(() => {
    setActiveMenu(null);
    setMobileOpen(false);
    dismissSearch();
  }, [pathname, dismissSearch]);

  useEffect(() => {
    if (isLoading) return;
    const updateBagCount = (event?: Event) => {
      const detail = (event as CustomEvent<{ itemCount?: number }> | undefined)?.detail;
      if (typeof detail?.itemCount === "number") {
        setBagCount(detail.itemCount);
        return;
      }
      fetch("/api/cart", { credentials: "include", cache: "no-store" })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((cart) => setBagCount(Number(cart.itemCount) || 0))
        .catch(() => setBagCount(0));
    };

    updateBagCount();
    window.addEventListener("yafa-cart-updated", updateBagCount);
    return () => {
      window.removeEventListener("yafa-cart-updated", updateBagCount);
    };
  }, [isAuthenticated, isLoading]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!headerRef.current?.contains(event.target as Node)) {
        setActiveMenu(null);
        dismissSearch();
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (searchOpen) {
        event.preventDefault();
        closeSearch();
        return;
      }
      if (!activeMenu) return;
      event.preventDefault();
      const trigger = document.getElementById(`nav-trigger-${activeMenu}`);
      setActiveMenu(null);
      trigger?.focus();
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [activeMenu, searchOpen, closeSearch, dismissSearch]);

  const handleHeaderBlur = (event: FocusEvent<HTMLElement>) => {
    if (!headerRef.current?.contains(event.relatedTarget as Node | null)) {
      setActiveMenu(null);
      dismissSearch();
    }
  };

  return (
    <header
      className="site-header"
      id="site-header"
      ref={headerRef}
      onMouseLeave={() => {
        cancelScheduledMenu();
        closeDesktopMenu();
      }}
      onBlur={handleHeaderBlur}
    >
      <AnnouncementBar />

      <nav className="utility-nav" aria-label="Store services">
        <div className="utility-nav__actions">
          <button
            type="button"
            aria-label="Search"
            aria-expanded={searchOpen}
            aria-controls={searchOpen ? "header-search-panel" : undefined}
            onClick={(event) => {
              if (!searchOpen) openSearch(event.currentTarget);
            }}
          >
            <ActionIcon type="search" />
          </button>
          <button type="button" aria-label={isAuthenticated ? "Sign out" : "Sign in"} onClick={() => isAuthenticated ? void logout() : openAuth()}>
            <ActionIcon type="account" />
          </button>
          <button className="utility-nav__bag-button" type="button" aria-label={`Open shopping bag, ${bagCount} ${bagCount === 1 ? "item" : "items"}`} onClick={() => window.dispatchEvent(new Event("yafa-cart-open"))}>
            <ActionIcon type="bag" />
            <span className="utility-nav__bag-count" aria-hidden="true">{bagCount}</span>
          </button>
          <Link className="utility-nav__contact" href="/contact">
            Stay in touch
          </Link>
        </div>
      </nav>

      <nav className="primary-nav" aria-label="Main navigation">
        <div className="primary-nav__brand-slot">
          <Link
            className="primary-nav__brand"
            href="/"
            aria-label="YAFA VANAM home"
            data-logo-target
          >
            <Wordmark />
          </Link>
        </div>

        <div className="primary-nav__desktop">
          <Link className="primary-nav__link" href="/shop">
            Shop All
          </Link>

          {menuTriggers.map((item) => (
            <button
              className="primary-nav__trigger"
              id={`nav-trigger-${item.key}`}
              key={item.key}
              type="button"
              aria-expanded={activeMenu === item.key}
              aria-controls={activeMenu === item.key ? "desktop-mega-menu" : undefined}
              onClick={() => toggleMegaMenu(item.key)}
              onMouseEnter={() => scheduleOpenMenu(item.key)}
              onFocus={() => openMegaMenu(item.key)}
              onKeyDown={(event) => handleTriggerKeyDown(event, item.key)}
            >
              {item.label}
            </button>
          ))}

          <Link className="primary-nav__kit" href="/build-my-kit">
            Build My Kit
          </Link>
        </div>

        <div className="primary-nav__mobile-actions">
          <button
            type="button"
            aria-label="Search"
            aria-expanded={searchOpen}
            aria-controls={searchOpen ? "header-search-panel" : undefined}
            onClick={(event) => {
              if (!searchOpen) openSearch(event.currentTarget);
            }}
          >
            <ActionIcon type="search" />
          </button>
          <button className="primary-nav__mobile-bag" type="button" aria-label={`Open shopping bag, ${bagCount} ${bagCount === 1 ? "item" : "items"}`} onClick={() => window.dispatchEvent(new Event("yafa-cart-open"))}>
            <ActionIcon type="bag" />
            {bagCount > 0 ? <span className="primary-nav__mobile-bag-count" aria-hidden="true">{bagCount}</span> : null}
          </button>
          <button
            className="menu-toggle"
            type="button"
            ref={mobileButtonRef}
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(true)}
          >
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>
        </div>
      </nav>

      {activeMenu && (
        <MegaMenu
          activeMenu={activeMenu}
          labelledBy={`nav-trigger-${activeMenu}`}
          onNavigate={closeDesktopMenu}
        />
      )}

      <MobileMenu
        open={mobileOpen}
        onClose={closeMobileMenu}
        onOpenSearch={(trigger) => {
          closeMobileMenu();
          openSearch(trigger);
        }}
      />

      <HeaderSearch open={searchOpen} onClose={closeSearch} />
    </header>
  );
}
