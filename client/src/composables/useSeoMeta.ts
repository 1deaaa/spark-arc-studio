import { watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useLocaleStore } from '@/components/stores/localeStore';

const SITE_NAME = 'SparkArc Studio';
const SITE_URL = 'https://arc.1dea.top/';
const SITE_ICON_URL = 'https://arc.1dea.top/icon.png';

function setMetaByName(name: string, content: string): void {
  let el = document.querySelector(`meta[name="${name}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('name', name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function setMetaByProperty(property: string, content: string): void {
  let el = document.querySelector(`meta[property="${property}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('property', property);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

export function useSeoMeta(): void {
  const { t } = useI18n();
  const localeStore = useLocaleStore();

  function applySeoMeta(): void {
    const title = t('seo.title');
    const description = t('seo.description');

    document.title = title;

    setMetaByName('description', description);
    setMetaByName('robots', 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1');
    setMetaByName('theme-color', '#0f172a');
    setMetaByName('twitter:title', title);
    setMetaByName('twitter:description', description);
    setMetaByName('twitter:image', SITE_ICON_URL);

    setMetaByProperty('og:title', title);
    setMetaByProperty('og:description', description);
    setMetaByProperty('og:type', 'website');
    setMetaByProperty('og:url', SITE_URL);
    setMetaByProperty('og:site_name', SITE_NAME);
    setMetaByProperty('og:image', SITE_ICON_URL);
    setMetaByProperty('og:image:alt', `${SITE_NAME} 图标`);
  }

  watch(() => localeStore.locale, () => {
    applySeoMeta();
  }, { immediate: true });
}
