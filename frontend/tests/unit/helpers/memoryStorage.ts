/** 용량 상한을 흉내 내는 Storage — 브라우저 localStorage 의 쿼터 초과를 재현한다 */
export class MemoryStorage implements Storage {
  [key: string]: unknown;
  failWith: Error | null = null;
  private readonly data = new Map<string, string>();

  constructor(private readonly capacity = Number.POSITIVE_INFINITY) {}

  get length(): number {
    return this.data.size;
  }

  clear(): void {
    this.data.clear();
  }

  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }

  key(index: number): string | null {
    return [...this.data.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.data.delete(key);
  }

  setItem(key: string, value: string): void {
    if (this.failWith) throw this.failWith;
    const next = String(value);
    if (this.usedExcept(key) + key.length + next.length > this.capacity) {
      throw new DOMException("쿼터 초과", "QuotaExceededError");
    }
    this.data.set(key, next);
  }

  private usedExcept(skip: string): number {
    let total = 0;
    for (const [k, v] of this.data) if (k !== skip) total += k.length + v.length;
    return total;
  }
}
