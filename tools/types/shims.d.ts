declare module '@octokit/rest' {
  export class Octokit {
    constructor(options?: any);
    actions: any;
    pulls: any;
  }
}

declare module 'adm-zip' {
  class AdmZip {
    constructor(path?: string);
    extractAllTo(targetPath: string, overwrite?: boolean): void;
  }
  export default AdmZip;
}
