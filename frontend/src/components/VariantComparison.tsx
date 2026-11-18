import { useEffect, useId, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import type {
  OptionLine,
  RecommendationOption,
  RecommendationView,
  Signal,
  SignalPolarity,
} from "../api/analysis";
import { Badge } from "@/components/ui/badge";
import {
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatPercent, formatPln, sourceText } from "./format";
import { variantName } from "./variantName";
import { signalMessage } from "./businessMessages";

type Props = {
  recommendation: RecommendationView;
  // The deadline of the inquiry (ISO date); null when it has none.
  expectedDeadline: string | null;
};

// The attribute column stays in view while the variants scroll; opaque so nothing shows through.
const STICKY = "sticky left-0 z-10 bg-card";

// Resolve signal codes in the current UI language, preserving unknown original labels.
const POLARITIES: [SignalPolarity, string][] = [
  ["positive", "✓"],
  ["risk", "⚠"],
  ["info", "ℹ"],
];

function lineText(line: OptionLine, t: TFunction): string {
  return t("recommendation.line", {
    quantity: line.quantity,
    code: line.product_code,
    name: line.product_name,
    source: sourceText(line, t),
    date: line.available_on,
    price: line.unit_price,
  });
}

function SignalLists({
  signals,
  cited,
}: {
  signals: Signal[];
  cited: readonly string[];
}) {
  const { t } = useTranslation();
  return (
    <>
      {POLARITIES.map(([polarity, mark]) => {
        const title = t(`recommendation.polarity.${polarity}`);
        const items = signals.filter((signal) => signal.polarity === polarity);
        if (items.length === 0) return null;
        return (
          <div key={polarity} className="recommendation__signals">
            <p className="orchestration__stage-title">{title}</p>
            <ul
              className={`recommendation__signal-list recommendation__signal-list--${polarity}`}
              aria-label={title}
            >
              {items.map((signal, index) => {
                const isCited = cited.includes(signal.code);
                return (
                  <li
                    key={`${signal.code}-${index}`}
                    className={isCited ? "recommendation__cited" : undefined}
                  >
                    <span aria-hidden="true">{mark} </span>
                    {signalMessage(signal, t)}
                    {isCited && (
                      <span className="recommendation__cited-tag">
                        {" · "}
                        {t("recommendation.cited")}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </>
  );
}

// Calendar days from the deadline to the fulfilment date (positive: late); both are ISO dates,
// compared as plain dates so the time zone cannot shift them.
function daysAfter(deadline: string, fulfilledOn: string): number | null {
  const toDay = (iso: string) => {
    const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
    return Date.UTC(year, month - 1, day);
  };
  const diff = (toDay(fulfilledOn) - toDay(deadline)) / 86_400_000;
  return Number.isFinite(diff) ? diff : null;
}

function deadlineRelation(
  fulfilledOn: string,
  deadline: string | null,
  t: TFunction,
): string {
  if (deadline === null) return t("variants.deadline.none");
  const days = daysAfter(deadline, fulfilledOn);
  if (days === null) return t("variants.deadline.none");
  if (days > 0) return t("variants.deadline.late", { count: days });
  if (days < 0) return t("variants.deadline.early", { count: -days });
  return t("variants.deadline.onDay");
}

// Variants side by side: attributes as rows, variants as columns, the recommended one first and
// outlined; the lines, cost and all signals of each variant are in the details below.
function VariantComparison({ recommendation, expectedDeadline }: Props) {
  const { t } = useTranslation();
  const choice = recommendation.choice;
  const chosen =
    recommendation.status === "completed" && choice !== null
      ? (recommendation.options.find(
          (option) => option.id === choice.option_id,
        ) ?? null)
      : null;
  const columns: RecommendationOption[] =
    chosen === null
      ? recommendation.options
      : [
          chosen,
          ...recommendation.options.filter((option) => option !== chosen),
        ];
  const cited = choice?.cited_signals ?? [];

  // Overflow signal: the scroll region is wider than its box when the variants do not all fit.
  const captionId = useId();
  const hintId = useId();
  const scrollRef = useRef<HTMLDivElement>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  const [overflowing, setOverflowing] = useState(false);
  const columnCount = columns.length;
  useEffect(() => {
    const container = scrollRef.current;
    if (container === null) return;
    const measure = () =>
      setOverflowing(container.scrollWidth > container.clientWidth);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    if (tableRef.current !== null) observer.observe(tableRef.current);
    return () => observer.disconnect();
  }, [columnCount]);

  if (columns.length === 0) return null;

  // The recommended column is outlined and carries a badge, so colour is not the only cue.
  const edge = (option: RecommendationOption) =>
    option === chosen ? "border-x-2 border-primary bg-accent" : "";

  const rows: {
    key: string;
    label: string;
    cell: (option: RecommendationOption) => string;
  }[] = [
    {
      key: "coverage",
      label: t("recommendation.coverage"),
      cell: (option) =>
        t("common.coverage", {
          covered: option.covered_quantity,
          requested: option.requested_quantity,
        }),
    },
    {
      key: "deadline",
      label: t("variants.row.deadline"),
      cell: (option) =>
        `${option.fulfilled_on}, ${deadlineRelation(option.fulfilled_on, expectedDeadline, t)}`,
    },
    {
      key: "value",
      label: t("recommendation.value"),
      cell: (option) => formatPln(option.value),
    },
    {
      key: "margin",
      label: t("recommendation.margin"),
      cell: (option) => formatPercent(option.margin_percent),
    },
    {
      key: "risks",
      label: t("variants.row.risks"),
      cell: (option) => {
        const risks = option.signals.filter(
          (signal) => signal.polarity === "risk",
        );
        return risks.length === 0
          ? t("variants.noRisks")
          : risks.map((s) => signalMessage(s, t)).join("\n");
      },
    },
    {
      key: "confidence",
      label: t("variants.row.confidence"),
      cell: (option) => t(`recommendation.band.${option.band}`),
    },
  ];

  return (
    <>
      {overflowing && (
        <p id={hintId} className="text-sm text-muted-foreground">
          {t("variants.scrollHint", { count: columns.length })}
        </p>
      )}
      <div
        ref={scrollRef}
        role="region"
        tabIndex={0}
        aria-labelledby={captionId}
        aria-describedby={overflowing ? hintId : undefined}
        data-slot="table-container"
        className="relative w-full overflow-x-auto rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring"
      >
        <table
          ref={tableRef}
          data-slot="table"
          className="w-full caption-bottom text-sm"
        >
          <TableCaption id={captionId} className="sr-only">
            {t("variants.caption")}
          </TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead scope="col" className={STICKY}>
                <span className="sr-only">{t("variants.attribute")}</span>
              </TableHead>
              {columns.map((option) => (
                <TableHead
                  key={option.id}
                  scope="col"
                  className={cn(
                    "min-w-40 py-2 align-top whitespace-normal",
                    edge(option),
                    option === chosen && "border-t-2",
                  )}
                >
                  <span className="block">{variantName(option, t)}</span>
                  {option === chosen && (
                    <Badge className="mt-1">{t("variants.recommended")}</Badge>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => (
              <TableRow key={row.key}>
                <TableHead
                  scope="row"
                  className={cn(STICKY, "text-muted-foreground")}
                >
                  {row.label}
                </TableHead>
                {columns.map((option) => (
                  <TableCell
                    key={option.id}
                    className={cn(
                      "min-w-40 align-top whitespace-pre-line",
                      edge(option),
                      option === chosen &&
                        index === rows.length - 1 &&
                        "border-b-2",
                    )}
                  >
                    {row.cell(option)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </table>
      </div>

      <div className="grid gap-2">
        {columns.map((option) => (
          <details
            key={option.id}
            open={option === chosen}
            className="rounded-md border bg-card px-3 py-2"
          >
            <summary className="cursor-pointer text-sm font-medium">
              {variantName(option, t)}
            </summary>
            <div className="mt-2 grid gap-2">
              <ul aria-label={t("recommendation.lines")} className="text-sm">
                {option.lines.map((line) => (
                  <li key={`${line.source}-${line.product_code}`}>
                    {lineText(line, t)}
                  </li>
                ))}
              </ul>
              <p className="text-sm">
                <span className="text-muted-foreground">
                  {t("recommendation.cost")}:{" "}
                </span>
                {formatPln(option.cost)}
              </p>
              <SignalLists
                signals={option.signals}
                cited={option === chosen ? cited : []}
              />
            </div>
          </details>
        ))}
      </div>
    </>
  );
}

export default VariantComparison;
