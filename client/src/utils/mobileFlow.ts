export function scrollToFlowStep(step: number) {
  const target = document.getElementById(`step-${step}`);
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
