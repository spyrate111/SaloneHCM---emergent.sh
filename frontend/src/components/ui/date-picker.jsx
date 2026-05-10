import * as React from "react";
import { format, parseISO } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { Calendar } from "./calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { cn } from "@/lib/utils";

export function DatePicker({ value, onChange, placeholder = "Pick a date", disabled, "data-testid": testId, className }) {
  const date = value ? (typeof value === "string" ? parseISO(value) : value) : undefined;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={testId}
          disabled={disabled}
          className={cn(
            "w-full inline-flex items-center justify-between bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm text-left focus:outline-none focus:ring-2 focus:ring-[#26547C] disabled:opacity-60",
            !date && "text-[#A1A5AB]",
            className
          )}
        >
          <span className="font-data">{date ? format(date, "PPP") : placeholder}</span>
          <CalendarIcon className="ml-2 h-4 w-4 text-[#A1A5AB]" strokeWidth={1.5} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0 bg-white" align="start">
        <Calendar
          mode="single"
          selected={date}
          onSelect={(d) => onChange?.(d ? format(d, "yyyy-MM-dd") : "")}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
