export type CartLine = {
  key: string;
  productId: string;
  variantId: string;
  name: string;
  slug: string;
  productType: string;
  currency: string;
  unitPrice: number;
  quantity: number;
  size: string | null;
  shade: string | null;
  image: string;
};

export type CartResponse = {
  items: CartLine[];
  itemCount: number;
  subtotal: number;
  currency: string;
};
