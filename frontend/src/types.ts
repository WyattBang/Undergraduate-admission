export type CourseScore = {
  course: string;
  score: number;
};

export type ProfileItem = {
  title: string;
  level?: string;
  intensity?: number;
};

export type PredictRequest = {
  target_school: string;
  target_major: string;
  english_test_type: "TOEFL" | "IELTS";
  english_score: number;
  curriculum_type: string;
  gpa: number;
  course_scores: CourseScore[];
  activities: ProfileItem[];
  awards: ProfileItem[];
  research: ProfileItem[];
  grad_year: number;
};

export type TopFactor = {
  factor: string;
  impact: "positive" | "negative";
  evidence: string;
};

export type SchoolRecommendation = {
  school: string;
  major: string;
  band: "reach" | "match" | "safe";
  probability: number;
};

export type PredictResponse = {
  admit_probability: number;
  confidence_band: "high" | "medium" | "low";
  top_factors: TopFactor[];
  weakness_diagnosis: string[];
  reach_match_safe_schools: SchoolRecommendation[];
  model_version: string;
  data_cutoff_date: string;
};
