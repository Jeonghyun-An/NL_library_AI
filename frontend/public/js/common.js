/* [S] LNB 접기/펼치기 */
(function () {
    var app         = document.querySelector('.skx-app');
    var collapseBtn = document.querySelector('[data-lnb-collapse]');
    var expandBtn   = document.querySelector('.skx-lnb__expand');
    if (!app) return;
    if (collapseBtn) collapseBtn.addEventListener('click', function () { app.classList.add('is-lnb-collapsed'); });
    if (expandBtn)   expandBtn.addEventListener('click',   function () { app.classList.remove('is-lnb-collapsed'); });
}());
/* [E] LNB 접기/펼치기 */

/* [S] 수직 탭 슬라이더 */
function skxInitVtabs(containerId, panelPrefix) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var btns = container.querySelectorAll('.skx-vtab');
    btns.forEach(function (btn, idx) {
        btn.addEventListener('click', function () {
            container.classList.toggle('is-second', idx === 1);
            btns.forEach(function (b, j) {
                b.classList.toggle('is-active', j === idx);
                b.setAttribute('aria-selected', j === idx ? 'true' : 'false');
            });
            var panelId = btn.getAttribute('data-vtab');
            document.querySelectorAll('[role="tabpanel"]').forEach(function (p) {
                if (p.id === panelPrefix + panelId) { p.removeAttribute('hidden'); }
                else { p.setAttribute('hidden', ''); }
            });
        });
    });
}
/* [E] 수직 탭 슬라이더 */

/* [S] 북마크 아이콘 토글 (기본 회색 / 활성 노랑) — ico-bookmark.svg 쓰는 모든 버튼 공통 */
(function () {
    // ico-bookmark.svg / ico-bookmark-on.svg 만 매칭 (ico-bookmark-menu.svg·ico-paper-bookmark.svg 제외)
    var IMG_SEL = 'img[src*="ico-bookmark.svg"], img[src*="ico-bookmark-on.svg"]';

    function setBookmark(btn, on) {
        btn.classList.toggle('is-active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        var img = btn.querySelector(IMG_SEL);
        if (img) {
            var base = (img.getAttribute('src') || '').replace(/ico-bookmark(-on)?\.svg.*$/, '');
            img.setAttribute('src', base + (on ? 'ico-bookmark-on.svg' : 'ico-bookmark.svg'));
        }
    }

    // 마크업의 초기 아이콘으로 활성 여부 판단해 상태 동기화
    document.querySelectorAll(IMG_SEL).forEach(function (img) {
        var btn = img.closest('button');
        if (btn) setBookmark(btn, /bookmark-on/.test(img.getAttribute('src') || ''));
    });

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('button');
        if (!btn || !btn.querySelector(IMG_SEL)) return;
        setBookmark(btn, !btn.classList.contains('is-active'));
    });
}());
/* [E] 북마크 아이콘 토글 */
