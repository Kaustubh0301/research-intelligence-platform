import type { Metadata } from "next";
import { FeatureMapClient } from "@/components/feature-map/FeatureMapClient";

export const metadata: Metadata = {
  title: "Feature Mapper — Research Intelligence Platform",
};

export default function FeatureMapPage() {
  return <FeatureMapClient />;
}
