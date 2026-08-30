export const analyticsEvents = {
  pageViewed: "page_viewed",
  collectionViewed: "collection_viewed",
  searchOpened: "search_opened",
  searchPerformed: "search_performed",
  productClicked: "product_clicked",
  productViewed: "product_viewed",
  shadeSelected: "shade_selected",
  wishlistAdded: "wishlist_added",
  productAddedToCart: "product_added_to_cart",
  productRemovedFromCart: "product_removed_from_cart",
  cartViewed: "cart_viewed",
  checkoutStarted: "checkout_started",
  shippingAdded: "shipping_added",
  paymentInfoAdded: "payment_info_added",
  purchaseCompleted: "purchase_completed",
  refundProcessed: "refund_processed",
  variantSelected: "variant_selected",
  addToCart: "add_to_cart",
  productReturned: "product_returned",
  shadeExchangeRequested: "shade_exchange_requested",
  // Yafa assistant lifecycle (Phase 3 section 44)
  yafaOpened: "yafa_opened",
  yafaMessageSent: "yafa_message_sent",
} as const;

export type AnalyticsEventName = typeof analyticsEvents[keyof typeof analyticsEvents];
export type AnalyticsProperties = Record<string, string | number | boolean | null | undefined>;
