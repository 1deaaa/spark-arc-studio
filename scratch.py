import re

with open('client/src/components/share/GlobalLoading.vue', 'r', encoding='utf-8') as f:
    gl_vue = f.read()

with open('client/src/components/share/GlobalLoading.scoped.css', 'r', encoding='utf-8') as f:
    gl_css = f.read()

loader_match = re.search(r'(<div class="spark-loader">.*?</svg>\s*</div>)', gl_vue, re.DOTALL)
if loader_match:
    spark_loader_html = loader_match.group(1)
else:
    print("No spark-loader found")
    exit(1)

new_gl_vue = gl_vue.replace(spark_loader_html, '<SparkLoaderAnimation />')
new_gl_vue = new_gl_vue.replace('import { ref, computed', 'import SparkLoaderAnimation from \'./SparkLoaderAnimation.vue\';\nimport { ref, computed')
with open('client/src/components/share/GlobalLoading.vue', 'w', encoding='utf-8') as f:
    f.write(new_gl_vue)

css_match = re.search(r'(/\* ===== 加载器容器 ===== \*/.*?)(/\* ===== 文字与信息 ===== \*/)', gl_css, re.DOTALL)
if css_match:
    loader_css = css_match.group(1)
else:
    print("CSS match failed")
    exit(1)

vars_css = '''
.spark-loader-wrapper {
  --loader-primary: var(--spark-primary);
  --loader-core-bright: var(--spark-primary-light);
  --loader-glow: var(--spark-primary-glow);
  --loader-orbit-outer: var(--spark-primary);
  --loader-orbit-inner: var(--spark-harmonious-a);
}

:root[data-theme="light"] .spark-loader-wrapper,
.light .spark-loader-wrapper {
  --loader-glow: color-mix(in srgb, var(--spark-primary), transparent 55%);
}
'''

vue_content = f'''<template>
  <div class="spark-loader-wrapper">
    {spark_loader_html}
  </div>
</template>

<style scoped>
{vars_css}
{loader_css}
</style>
'''

with open('client/src/components/share/SparkLoaderAnimation.vue', 'w', encoding='utf-8') as f:
    f.write(vue_content)

print("Extraction complete.")
