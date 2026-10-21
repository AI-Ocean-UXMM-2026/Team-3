import { describe, expect, it } from "vitest";
import { matchTownships, findTownship } from "../src/townships.ts";
import { DictionaryGeocoder } from "../src/places.ts";

describe("Layer 2: Yangon township dictionary (HLR-04)", () => {
  it.each([
    ["ကမာရွတ် ဆင်ရေကန်လမ်း", "kamayut"],
    ["Bahan Tsp", "bahan"],
    ["sanchaung township", "sanchaung"],
    ["ဗဟန်းမြို့နယ်", "bahan"],
    ["မင်္ဂလာဒုံ ဈေးနား", "mingaladon"],
    ["မဂ်လာဒုံ", "mingaladon"],
  ])("matches %j", (text, id) => {
    expect(findTownship(text)?.id).toBe(id);
  });

  it("prefers the longest name, so North Dagon is not read as Dagon", () => {
    expect(findTownship("မြောက်ဒဂုံ ၃၅ ရပ်ကွက်")?.id).toBe("north-dagon");
    expect(findTownship("လှိုင်သာယာ")?.id).toBe("hlaing-tharyar");
    expect(findTownship("ဒဂုံဆိပ်ကမ်း")?.id).toBe("dagon-seikkan");
  });

  it("respects Burmese syllable edges (အလုံး is not Ahlone)", () => {
    expect(findTownship("အလုံးလိုက် ယူမယ်")).toBeNull();
    expect(findTownship("အလုံ ကမ်းနားလမ်း")?.id).toBe("ahlone");
  });

  it("maps well-known areas to their township", () => {
    expect(findTownship("လှည်းတန်း")?.id).toBe("kamayut");
    expect(findTownship("Hledan junction")?.id).toBe("kamayut");
    expect(findTownship("၈ မိုင်")?.id).toBe("mayangon");
  });

  it("reports every township mentioned", () => {
    expect(matchTownships("တာမွေ ကနေ တောင်ဒဂုံ ပြောင်းမယ်").map((m) => m.township.id)).toEqual([
      "tamwe",
      "south-dagon",
    ]);
  });

  it("does not count a road named after a township as that township", () => {
    expect(matchTownships("လှိုင် အင်းစိန်လမ်း").map((m) => m.township.id)).toEqual(["hlaing"]);
    expect(matchTownships("Kamayut, Insein Road").map((m) => m.township.id)).toEqual(["kamayut"]);
  });

  it("does not match English names inside other words", () => {
    expect(findTownship("Dalai")).toBeNull();
  });
});

describe("Layer 2: places we can put on the map", () => {
  const geocoder = new DictionaryGeocoder();

  it("finds a known landmark and its township", async () => {
    const hit = await geocoder.locate("Junction Square နောက်ဘက်", "kamayut");
    expect(hit).toMatchObject({ name: "Junction Square", townshipId: "kamayut", kind: "landmark" });
    expect(hit?.lat).toBeTypeOf("number");
  });

  it("finds a major road in Burmese", async () => {
    expect(await geocoder.locate("ပြည်လမ်းမကြီးပေါ်", "kamayut")).toMatchObject({ kind: "road", name: "Pyay Road" });
  });

  it("knows Kaba Aye Pagoda Road also runs through Yankin", async () => {
    expect(await geocoder.locate("Kaba Aye Pagoda Road", "yankin")).toMatchObject({ townshipId: "yankin" });
  });

  it("returns null for unknown places", async () => {
    expect(await geocoder.locate("အဆွေတော်နား", "tamwe")).toBeNull();
  });

  it("prefers a place in the stated township when the name repeats", async () => {
    expect(await geocoder.locate("Ocean", "tamwe")).toMatchObject({ townshipId: "tamwe" });
    expect(await geocoder.locate("Ocean", "north-okkalapa")).toMatchObject({ townshipId: "north-okkalapa" });
  });
});
