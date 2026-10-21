declare module "rabbit-node" {
  const rabbit: { zg2uni(text: string): string; uni2zg(text: string): string };
  export default rabbit;
}
declare module "myanmar-tools" {
  export class ZawgyiDetector {
    getZawgyiProbability(text: string): number;
  }
  const tools: { ZawgyiDetector: typeof ZawgyiDetector };
  export default tools;
}
