import type { BookChunkGroup } from "~/types/search";

export interface CartItem {
  book_id: string;
  title: string;
  author: string;
}

const STORAGE_KEY = "cart";

// 장바구니 — 대출 신청한 도서 보관 (클라이언트 상태 + localStorage 영속).
// useState 로 컴포넌트 간 공유 (TopResult 에서 담고, 좌측 패널에서 표시).
export function useCart() {
  const cart = useState<CartItem[]>("cart", () => {
    if (process.client) {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) return JSON.parse(raw) as CartItem[];
      } catch {
        /* ignore */
      }
    }
    return [];
  });

  function _persist() {
    if (process.client) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cart.value));
    }
  }

  // 담기. 이미 있으면 false, 새로 담으면 true.
  function addToCart(book: BookChunkGroup): boolean {
    const id = book?.book_id;
    if (!id) return false;
    if (cart.value.some((b) => b.book_id === id)) return false;
    const info = book.book_info;
    cart.value = [
      ...cart.value,
      {
        book_id: id,
        title: info?.title || id,
        author: info?.personal_author || info?.corporate_author || "",
      },
    ];
    _persist();
    return true;
  }

  function removeFromCart(bookId: string) {
    cart.value = cart.value.filter((b) => b.book_id !== bookId);
    _persist();
  }

  function clearCart() {
    cart.value = [];
    _persist();
  }

  return { cart, addToCart, removeFromCart, clearCart };
}
