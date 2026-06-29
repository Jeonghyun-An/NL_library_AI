const bookmarkedIds = ref(new Set<string>())

export function useBookmark() {
  function isBookmarked(id: string): boolean {
    return bookmarkedIds.value.has(id)
  }

  function toggleBookmark(id: string): void {
    const next = new Set(bookmarkedIds.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    bookmarkedIds.value = next
  }

  function bookmarkIcon(id: string): string {
    return isBookmarked(id) ? '/img/ico-bookmark-on.svg' : '/img/ico-bookmark.svg'
  }

  return { isBookmarked, toggleBookmark, bookmarkIcon }
}
