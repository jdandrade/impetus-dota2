"use client";

import { useMemo } from "react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
} from "recharts";
import { type OpenDotaPlayer } from "@/lib/opendota";

interface NetWorthGraphProps {
    players: OpenDotaPlayer[];
}

interface DataPoint {
    time: number;
    goldDiff: number;
}

function formatGold(value: number): string {
    if (Math.abs(value) >= 1000) {
        return `${(value / 1000).toFixed(1)}k`;
    }
    return value.toString();
}

export default function NetWorthGraph({ players }: NetWorthGraphProps) {
    const data = useMemo(() => {
        const radiantPlayers = players.filter((p) => p.isRadiant);
        const direPlayers = players.filter((p) => !p.isRadiant);

        const hasGoldData = players.some((p) => p.gold_t && p.gold_t.length > 0);
        if (!hasGoldData) {
            return null;
        }

        const maxLength = Math.max(...players.map((p) => p.gold_t?.length ?? 0));

        const dataPoints: DataPoint[] = [];

        for (let i = 0; i < maxLength; i++) {
            const radiantGold = radiantPlayers.reduce(
                (sum, p) => sum + (p.gold_t?.[i] ?? 0),
                0
            );
            const direGold = direPlayers.reduce(
                (sum, p) => sum + (p.gold_t?.[i] ?? 0),
                0
            );

            dataPoints.push({
                time: i,
                goldDiff: radiantGold - direGold,
            });
        }

        return dataPoints;
    }, [players]);

    const dataEndTime = data ? data.length - 1 : 0;

    const xAxisTicks = useMemo(() => {
        const ticks: number[] = [];
        for (let i = 0; i <= dataEndTime; i += 5) {
            ticks.push(i);
        }
        return ticks;
    }, [dataEndTime]);

    if (!data) {
        return (
            <div className="glass rounded-xl p-6 text-center">
                <h3 className="text-lg font-semibold text-cyber-text mb-2">
                    Gold Advantage
                </h3>
                <p className="text-cyber-text-muted">
                    Graph unavailable - replay not yet parsed by OpenDota.
                    <br />
                    <span className="text-sm">
                        Time-series data requires replay parsing. Try refreshing in a few minutes.
                    </span>
                </p>
            </div>
        );
    }

    const maxDiff = Math.max(...data.map((d) => Math.abs(d.goldDiff)));
    const yAxisMax = Math.ceil(maxDiff / 5000) * 5000 || 5000;

    return (
        <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-cyber-text">
                    Gold Advantage
                </h3>
                <div className="flex gap-4 text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                        <span className="text-cyber-text-muted">Radiant</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-red-500" />
                        <span className="text-cyber-text-muted">Dire</span>
                    </div>
                </div>
            </div>

            <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                        data={data}
                        margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                    >
                        <defs>
                            <linearGradient id="splitColor" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.5} />
                                <stop offset="50%" stopColor="#22c55e" stopOpacity={0.1} />
                                <stop offset="50%" stopColor="#ef4444" stopOpacity={0.1} />
                                <stop offset="100%" stopColor="#ef4444" stopOpacity={0.5} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis
                            dataKey="time"
                            type="number"
                            stroke="#9ca3af"
                            tick={{ fill: "#9ca3af", fontSize: 12 }}
                            tickFormatter={(value) => `${value}m`}
                            ticks={xAxisTicks}
                            domain={[0, dataEndTime]}
                        />
                        <YAxis
                            stroke="#9ca3af"
                            tick={{ fill: "#9ca3af", fontSize: 12 }}
                            tickFormatter={formatGold}
                            domain={[-yAxisMax, yAxisMax]}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: "#1f2937",
                                border: "1px solid #374151",
                                borderRadius: "8px",
                            }}
                            labelStyle={{ color: "#f3f4f6" }}
                            labelFormatter={(label) => `${label}:00`}
                            content={({ active, payload, label }) => {
                                if (!active || !payload || payload.length === 0) return null;
                                const value = payload[0]?.payload?.goldDiff as number;
                                if (value === undefined) return null;
                                const isRadiant = value >= 0;
                                const color = isRadiant ? "#22c55e" : "#ef4444";
                                const team = isRadiant ? "Radiant" : "Dire";
                                return (
                                    <div style={{
                                        backgroundColor: "#1f2937",
                                        border: "1px solid #374151",
                                        borderRadius: "8px",
                                        padding: "8px 12px",
                                    }}>
                                        <p style={{ color: "#f3f4f6", marginBottom: 4 }}>{label}:00</p>
                                        <p style={{ color, margin: 0 }}>
                                            {team}: {value > 0 ? "+" : ""}{formatGold(value)}
                                        </p>
                                    </div>
                                );
                            }}
                        />
                        <ReferenceLine y={0} stroke="#6b7280" strokeWidth={2} />
                        <Area
                            type="monotone"
                            dataKey="goldDiff"
                            stroke="none"
                            fill="url(#splitColor)"
                            fillOpacity={1}
                            baseValue={0}
                            tooltipType="none"
                        />
                        {/* Green line for positive values */}
                        <Area
                            type="monotone"
                            dataKey="goldDiff"
                            stroke="#22c55e"
                            strokeWidth={2}
                            fill="none"
                            dot={false}
                            activeDot={{ r: 4, fill: "#22c55e" }}
                            data={data.map(d => ({ ...d, goldDiff: d.goldDiff >= 0 ? d.goldDiff : null }))}
                            tooltipType="none"
                        />
                        {/* Red line for negative values - this one shows in tooltip */}
                        <Area
                            type="monotone"
                            dataKey="goldDiff"
                            stroke="#ef4444"
                            strokeWidth={2}
                            fill="none"
                            dot={false}
                            activeDot={{ r: 4, fill: "#ef4444" }}
                            data={data.map(d => ({ ...d, goldDiff: d.goldDiff < 0 ? d.goldDiff : null }))}
                            tooltipType="none"
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
