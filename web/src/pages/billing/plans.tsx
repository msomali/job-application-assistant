import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Free",
    price: "$0",
    features: ["10 scrapes/day", "20 analyses/day", "5 generations/day", "1 user"],
    current: true,
  },
  {
    name: "Pro",
    price: "$29/mo",
    features: ["100 scrapes/day", "200 analyses/day", "50 generations/day", "5 users", "Priority support"],
    current: false,
  },
  {
    name: "Enterprise",
    price: "Custom",
    features: ["Unlimited scrapes", "Unlimited analyses", "Unlimited generations", "Unlimited users", "SSO", "Dedicated support"],
    current: false,
  },
];

export function Component() {
  return (
    <div className="max-w-3xl">
      <div className="grid grid-cols-3 gap-4">
        {plans.map((plan) => (
          <Card key={plan.name} className={plan.current ? "border-primary" : ""}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{plan.name}</CardTitle>
                {plan.current && <Badge>Current</Badge>}
              </div>
              <div className="text-2xl font-bold">{plan.price}</div>
            </CardHeader>
            <CardContent className="space-y-2">
              {plan.features.map((f) => (
                <div key={f} className="flex items-center gap-2 text-sm">
                  <Check className="h-4 w-4 text-green-600" /> {f}
                </div>
              ))}
              <Button
                className="mt-4 w-full"
                variant={plan.current ? "outline" : "default"}
                disabled={plan.current}
              >
                {plan.current ? "Current plan" : "Upgrade"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Payment integration coming soon. Plans shown for illustration.
      </p>
    </div>
  );
}
