export const version: string = '1.5.0';
export const [major, minor, patch]: number[] = version
  .split('.')
  .map(s => parseInt(s));

// Taken from https://semver.org/
export const semverRegex = new RegExp(
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/gm,
);

export const isOutdatedClientVersion = (val: string): boolean => {
  const [apiMajor, apiMinor] = val.split('.').map(s => parseInt(s));
  return apiMajor != major || (apiMajor === major && apiMinor > minor);
};
