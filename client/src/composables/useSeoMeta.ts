import { watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useLocaleStore } from '@/components/stores/localeStore';

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
    setMetaByName('twitter:title', title);
    setMetaByName('twitter:description', description);

    setMetaByProperty('og:title', title);
    setMetaByProperty('og:description', description);
  }

  watch(() => localeStore.locale, () => {
    applySeoMeta();
  }, { immediate: true });
}
