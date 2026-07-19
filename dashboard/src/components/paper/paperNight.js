/* Dag/nat for Warm Paper-tabletten: nat = efter solnedgang eller før
   solopgang (weather.sunrise/sunset, lokal ISO). Uden sol-tider: 22–06. */
const hourOf = (iso) => {
  const [h, m] = iso.slice(11, 16).split(':');
  return +h + +m / 60;
};

export function isNight(now, weather) {
  const t = now.getHours() + now.getMinutes() / 60;
  if (!weather?.sunrise || !weather?.sunset) return t >= 22 || t < 6;
  return t < hourOf(weather.sunrise) || t >= hourOf(weather.sunset);
}
