import { Type } from "@sinclair/typebox";

export default function (pi: any) {
  pi.registerTool({
    name: "beep",
    description: "Play a beep sound in the user's browser. Use when the user asks for an audible alert, notification, or beep.",
    parameters: Type.Object({
      frequency: Type.Optional(Type.Number({ description: "Frequency in Hz (default 440)" })),
      duration: Type.Optional(Type.Number({ description: "Duration in milliseconds (default 200)" })),
    }),
    async execute(_toolCallId: string, params: { frequency?: number; duration?: number }) {
      const freq = params.frequency || 440;
      const dur = params.duration || 600;
      return {
        content: [{ type: "text", text: `Beep! (${freq}Hz, ${dur}ms)` }],
        details: {},
      };
    },
  });
}
