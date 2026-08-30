"use client";

import { useState } from "react";

const announcements = [
  "COMPLIMENTARY SHIPPING ON ORDERS OVER ₹1,999.",
  "EASY RETURNS WITHIN 14 DAYS.",
  "NEW RITUALS, MADE FOR EVERYDAY.",
];

export default function AnnouncementBar() {
  const [activeAnnouncement, setActiveAnnouncement] = useState(0);

  const moveAnnouncement = (direction: -1 | 1) => {
    setActiveAnnouncement((current) =>
      (current + direction + announcements.length) % announcements.length,
    );
  };

  return (
    <aside className="announcement-bar" aria-label="Store announcements">
      <button
        className="announcement-bar__control"
        type="button"
        onClick={() => moveAnnouncement(-1)}
        aria-label="Previous announcement"
      >
        <span aria-hidden="true">‹</span>
      </button>
      <p className="announcement-bar__message" aria-live="polite" title={announcements[activeAnnouncement]}>
        {announcements[activeAnnouncement]}
      </p>
      <button
        className="announcement-bar__control"
        type="button"
        onClick={() => moveAnnouncement(1)}
        aria-label="Next announcement"
      >
        <span aria-hidden="true">›</span>
      </button>
    </aside>
  );
}
