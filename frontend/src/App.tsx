import { FormEvent, useEffect, useMemo, useState } from "react";

import { fetchMajors, fetchSchools, predict } from "./api";
import ProbabilityGauge from "./components/ProbabilityGauge";
import type { PredictRequest, PredictResponse, ProfileItem } from "./types";

function parseCourses(input: string): PredictRequest["course_scores"] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [course, score] = line.split(":");
      return { course: (course || "Course").trim(), score: Number(score || "85") };
    })
    .filter((item) => Number.isFinite(item.score));
}

function parseProfileItems(input: string): ProfileItem[] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [title, level, intensity] = line.split("|");
      return {
        title: (title || "经历").trim(),
        level: level?.trim() || "school",
        intensity: intensity ? Number(intensity) : 6,
      };
    })
    .filter((item) => !!item.title);
}

export default function App() {
  const [schools, setSchools] = useState<string[]>([]);
  const [majors, setMajors] = useState<string[]>([]);

  const [targetSchool, setTargetSchool] = useState("Harvard University");
  const [targetMajor, setTargetMajor] = useState("CS");
  const [englishType, setEnglishType] = useState<"TOEFL" | "IELTS">("TOEFL");
  const [englishScore, setEnglishScore] = useState("108");
  const [curriculum, setCurriculum] = useState("AP");
  const [gpa, setGpa] = useState("3.9");
  const [gradYear, setGradYear] = useState("2026");

  const [courseText, setCourseText] = useState("AP Calculus:95\nAP Physics:93\nAP English:92");
  const [activityText, setActivityText] = useState("机器人社团|national|8\n公益志愿|school|7");
  const [awardText, setAwardText] = useState("数学竞赛|regional|7");
  const [researchText, setResearchText] = useState("AI课题|school|6");

  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const [schoolsRes, majorsRes] = await Promise.all([fetchSchools(), fetchMajors()]);
        setSchools(schoolsRes);
        setMajors(majorsRes);
        if (schoolsRes.length > 0) {
          setTargetSchool((prev) => (schoolsRes.includes(prev) ? prev : schoolsRes[0]));
        }
        if (majorsRes.length > 0) {
          setTargetMajor((prev) => (majorsRes.includes(prev) ? prev : majorsRes[0]));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载学校和专业失败");
      }
    };
    void run();
  }, []);

  const payload = useMemo<PredictRequest>(
    () => ({
      target_school: targetSchool,
      target_major: targetMajor,
      english_test_type: englishType,
      english_score: Number(englishScore),
      curriculum_type: curriculum,
      gpa: Number(gpa),
      course_scores: parseCourses(courseText),
      activities: parseProfileItems(activityText),
      awards: parseProfileItems(awardText),
      research: parseProfileItems(researchText),
      grad_year: Number(gradYear),
    }),
    [
      targetSchool,
      targetMajor,
      englishType,
      englishScore,
      curriculum,
      gpa,
      courseText,
      activityText,
      awardText,
      researchText,
      gradYear,
    ]
  );

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await predict(payload);
      setResult(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "预测失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <h1>美本名校申请概率预测</h1>
        <p>输入你的申请背景，获得录取概率、短板诊断与冲稳保建议。</p>
      </header>

      <main className="layout">
        <form className="panel form-panel" onSubmit={onSubmit}>
          <h2>申请背景表单</h2>

          <label>
            目标学校
            <select value={targetSchool} onChange={(e) => setTargetSchool(e.target.value)}>
              {schools.map((school) => (
                <option key={school} value={school}>
                  {school}
                </option>
              ))}
            </select>
          </label>

          <label>
            目标专业
            <select value={targetMajor} onChange={(e) => setTargetMajor(e.target.value)}>
              {majors.map((major) => (
                <option key={major} value={major}>
                  {major}
                </option>
              ))}
            </select>
          </label>

          <div className="inline-grid">
            <label>
              语言考试
              <select value={englishType} onChange={(e) => setEnglishType(e.target.value as "TOEFL" | "IELTS")}>
                <option value="TOEFL">TOEFL</option>
                <option value="IELTS">IELTS</option>
              </select>
            </label>

            <label>
              分数
              <input value={englishScore} onChange={(e) => setEnglishScore(e.target.value)} />
            </label>
          </div>

          <div className="inline-grid">
            <label>
              课程体系
              <select value={curriculum} onChange={(e) => setCurriculum(e.target.value)}>
                <option value="AP">AP</option>
                <option value="IB">IB</option>
                <option value="A-Level">A-Level</option>
                <option value="Other">Other</option>
              </select>
            </label>

            <label>
              GPA
              <input value={gpa} onChange={(e) => setGpa(e.target.value)} />
            </label>

            <label>
              毕业年份
              <input value={gradYear} onChange={(e) => setGradYear(e.target.value)} />
            </label>
          </div>

          <label>
            课程成绩（每行：课程:分数）
            <textarea value={courseText} onChange={(e) => setCourseText(e.target.value)} />
          </label>

          <label>
            活动经历（每行：标题|level|intensity）
            <textarea value={activityText} onChange={(e) => setActivityText(e.target.value)} />
          </label>

          <label>
            奖项经历（每行：标题|level|intensity）
            <textarea value={awardText} onChange={(e) => setAwardText(e.target.value)} />
          </label>

          <label>
            科研经历（每行：标题|level|intensity）
            <textarea value={researchText} onChange={(e) => setResearchText(e.target.value)} />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "正在计算..." : "生成预测报告"}
          </button>
        </form>

        <section className="panel result-panel">
          <h2>预测结果</h2>
          {error && <div className="error">{error}</div>}
          {!error && !result && <p>提交表单后将在这里展示结果。</p>}
          {result && (
            <>
              <ProbabilityGauge probability={result.admit_probability} confidenceBand={result.confidence_band} />

              <div className="subsection">
                <h3>关键影响因子</h3>
                <ul>
                  {result.top_factors.map((factor) => (
                    <li key={factor.factor + factor.impact}>
                      <strong className={factor.impact}>{factor.factor}</strong> - {factor.evidence}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="subsection">
                <h3>短板诊断</h3>
                <ul>
                  {result.weakness_diagnosis.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="subsection">
                <h3>冲稳保建议</h3>
                <table>
                  <thead>
                    <tr>
                      <th>学校</th>
                      <th>专业</th>
                      <th>档位</th>
                      <th>概率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.reach_match_safe_schools.map((item) => (
                      <tr key={`${item.school}-${item.band}`}>
                        <td>{item.school}</td>
                        <td>{item.major}</td>
                        <td>{item.band}</td>
                        <td>{Math.round(item.probability * 100)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="meta">模型版本：{result.model_version} | 数据截止：{result.data_cutoff_date}</p>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
