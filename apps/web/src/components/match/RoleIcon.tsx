/**
 * Role Icon Component
 * 
 * Displays role icons based on net worth ranking (Position 1-5)
 */

import { Sword, Crosshair, Shield, Backpack, Heart } from "lucide-react";

type Role = "carry" | "mid" | "offlane" | "support" | "hard_support";

interface RoleIconProps {
    role: Role;
    size?: number;
    className?: string;
}

const ROLE_CONFIG: Record<Role, { Icon: typeof Sword; color: string; label: string }> = {
    carry: {
        Icon: Sword,
        color: "text-amber-400",
        label: "Position 1 (Carry)",
    },
    mid: {
        Icon: Crosshair,
        color: "text-cyan-400",
        label: "Position 2 (Mid)",
    },
    offlane: {
        Icon: Shield,
        color: "text-green-400",
        label: "Position 3 (Offlane)",
    },
    support: {
        Icon: Backpack,
        color: "text-purple-400",
        label: "Position 4 (Soft Support)",
    },
    hard_support: {
        Icon: Heart,
        color: "text-pink-400",
        label: "Position 5 (Hard Support)",
    },
};

export default function RoleIcon({ role, size = 16, className = "" }: RoleIconProps) {
    const { Icon, color, label } = ROLE_CONFIG[role] || ROLE_CONFIG.support;

    return (
        <div className={`inline-flex items-center justify-center ${className}`} title={label}>
            <Icon className={`${color}`} size={size} />
        </div>
    );
}

export { ROLE_CONFIG };
export type { Role };
